import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Stock } from './stock.schema';

type ChartPoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type ChartResponse = {
  symbol: string;
  source: 'yahoo' | 'naver';
  currency: string;
  points: ChartPoint[];
};

type YahooQuote = {
  open?: Array<number | null>;
  high?: Array<number | null>;
  low?: Array<number | null>;
  close?: Array<number | null>;
  volume?: Array<number | null>;
};

type YahooChartResult = {
  meta?: {
    currency?: string;
    symbol?: string;
  };
  timestamp?: number[];
  indicators?: {
    quote?: YahooQuote[];
  };
};

const CHART_RANGES = new Set(['1mo', '3mo', '6mo', '1y']);

@Injectable()
export class StocksService {
  constructor(@InjectModel(Stock.name) private stockModel: Model<Stock>) {}

  async findAll(
    page = 1,
    limit = 50,
    market?: string,
  ): Promise<{ data: Stock[]; total: number; page: number; limit: number }> {
    const filter = market ? { market } : {};
    const skip = (page - 1) * limit;
    const [data, total] = await Promise.all([
      this.stockModel
        .find(filter)
        .sort({ position_pct: 1 })
        .skip(skip)
        .limit(limit)
        .exec(),
      this.stockModel.countDocuments(filter).exec(),
    ]);
    return { data, total, page, limit };
  }

  async findChart(
    market: string,
    code: string,
    range = '6mo',
  ): Promise<ChartResponse> {
    const safeRange = CHART_RANGES.has(range) ? range : '6mo';
    const symbols = this.getChartSymbols(market, code);

    for (const symbol of symbols) {
      const yahoo = await this.fetchYahooChart(symbol, safeRange);
      if (yahoo.points.length) {
        return yahoo;
      }
    }

    if (market === 'KOSPI') {
      const naver = await this.fetchNaverChart(code, safeRange);
      if (naver.points.length) {
        return naver;
      }
    }

    return {
      symbol: symbols[0] ?? code,
      source: 'yahoo',
      currency: market === 'KOSPI' ? 'KRW' : 'USD',
      points: [],
    };
  }

  private getChartSymbols(market: string, code: string): string[] {
    const normalizedCode = code.trim().toUpperCase();
    if (market === 'KOSPI' && /^\d+$/.test(normalizedCode)) {
      return [`${normalizedCode}.KS`, `${normalizedCode}.KQ`];
    }
    return [normalizedCode];
  }

  private async fetchYahooChart(
    symbol: string,
    range: string,
  ): Promise<ChartResponse> {
    try {
      const url = new URL(
        `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`,
      );
      url.searchParams.set('range', range);
      url.searchParams.set('interval', '1d');

      const response = await fetch(url, {
        headers: {
          Accept: 'application/json',
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        signal: AbortSignal.timeout(8000),
      });

      if (!response.ok) {
        throw new Error(`Yahoo chart failed: ${response.status}`);
      }

      const payload = (await response.json()) as {
        chart?: { result?: YahooChartResult[] };
      };
      const result = payload.chart?.result?.[0];
      const quote = result?.indicators?.quote?.[0];
      const timestamps = result?.timestamp ?? [];
      const points = timestamps
        .map((timestamp, index) => ({
          date: new Date(timestamp * 1000).toISOString().slice(0, 10),
          open: Number(quote?.open?.[index]),
          high: Number(quote?.high?.[index]),
          low: Number(quote?.low?.[index]),
          close: Number(quote?.close?.[index]),
          volume: Number(quote?.volume?.[index] ?? 0),
        }))
        .filter((point) =>
          [point.open, point.high, point.low, point.close].every((value) =>
            Number.isFinite(value),
          ),
        );

      return {
        symbol: result?.meta?.symbol ?? symbol,
        source: 'yahoo',
        currency: result?.meta?.currency ?? 'USD',
        points,
      };
    } catch {
      return { symbol, source: 'yahoo', currency: 'USD', points: [] };
    }
  }

  private async fetchNaverChart(
    code: string,
    range: string,
  ): Promise<ChartResponse> {
    try {
      const end = new Date();
      const start = new Date(end);
      const monthMap: Record<string, number> = {
        '1mo': 1,
        '3mo': 3,
        '6mo': 6,
        '1y': 12,
      };
      start.setMonth(start.getMonth() - (monthMap[range] ?? 6));

      const url = new URL('https://fchart.stock.naver.com/siseJson.nhn');
      url.searchParams.set('symbol', code);
      url.searchParams.set('requestType', '1');
      url.searchParams.set('startTime', this.formatCompactDate(start));
      url.searchParams.set('endTime', this.formatCompactDate(end));
      url.searchParams.set('timeframe', 'day');

      const response = await fetch(url, {
        headers: {
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        signal: AbortSignal.timeout(8000),
      });
      const text = await response.text();
      const rowPattern =
        /\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)/g;
      const points: ChartPoint[] = [];
      let match: RegExpExecArray | null;
      while ((match = rowPattern.exec(text)) !== null) {
        points.push({
          date: `${match[1].slice(0, 4)}-${match[1].slice(4, 6)}-${match[1].slice(6, 8)}`,
          open: Number(match[2]),
          high: Number(match[3]),
          low: Number(match[4]),
          close: Number(match[5]),
          volume: Number(match[6]),
        });
      }

      return {
        symbol: `NAVER:${code}`,
        source: 'naver',
        currency: 'KRW',
        points,
      };
    } catch {
      return {
        symbol: `NAVER:${code}`,
        source: 'naver',
        currency: 'KRW',
        points: [],
      };
    }
  }

  private formatCompactDate(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}${month}${day}`;
  }
}
