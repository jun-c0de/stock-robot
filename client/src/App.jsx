import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3001';

const MARKETS = [
  { key: 'KOSPI', label: '국내주식', sub: 'KIS 수급 기반' },
  { key: 'SP500', label: '해외주식', sub: '모멘텀 기반' },
];

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'quality', label: '매수 후보' },
  { key: 'supply', label: '수급 동반' },
  { key: 'risk', label: '리스크 낮음' },
];

const CHART_RANGES = [
  { key: '1mo', label: '1M' },
  { key: '3mo', label: '3M' },
  { key: '6mo', label: '6M' },
  { key: '1y', label: '1Y' },
];

const SAMPLE_STOCKS = [
  {
    _id: 'sample-005930',
    market: 'KOSPI',
    currency: 'KRW',
    name: '삼성전자',
    code: '005930',
    price: 81500,
    position_pct: 28,
    rsi: 37,
    disparity: 96.2,
    buy_target: 79800,
    sell_target: 86600,
    stop_loss: 77300,
    frgn_net: 842000,
    inst_net: 210000,
    pension_net: 62000,
    fin_invest_net: -18000,
    individual_net: -940000,
    is_double_buy: true,
    updatedAt: new Date().toISOString(),
  },
  {
    _id: 'sample-000660',
    market: 'KOSPI',
    currency: 'KRW',
    name: 'SK하이닉스',
    code: '000660',
    price: 286500,
    position_pct: 51,
    rsi: 61,
    disparity: 109.5,
    buy_target: 271000,
    sell_target: 309000,
    stop_loss: 263000,
    frgn_net: 125000,
    inst_net: -38000,
    pension_net: 21000,
    fin_invest_net: -14000,
    individual_net: -92000,
    is_double_buy: false,
    updatedAt: new Date().toISOString(),
  },
  {
    _id: 'sample-035420',
    market: 'KOSPI',
    currency: 'KRW',
    name: 'NAVER',
    code: '035420',
    price: 191200,
    position_pct: 22,
    rsi: 34,
    disparity: 93.4,
    buy_target: 185000,
    sell_target: 207000,
    stop_loss: 178500,
    frgn_net: -44000,
    inst_net: 98000,
    pension_net: 47000,
    fin_invest_net: 12000,
    individual_net: -58000,
    is_double_buy: false,
    updatedAt: new Date().toISOString(),
  },
  {
    _id: 'sample-nvda',
    market: 'SP500',
    currency: 'USD',
    name: 'NVIDIA',
    code: 'NVDA',
    price: 214.32,
    position_pct: 63,
    rsi: 58,
    disparity: 112.8,
    buy_target: 203.1,
    sell_target: 231.5,
    stop_loss: 196.7,
    frgn_net: 0,
    inst_net: 0,
    pension_net: 0,
    fin_invest_net: 0,
    individual_net: 0,
    is_double_buy: false,
    updatedAt: new Date().toISOString(),
  },
  {
    _id: 'sample-aapl',
    market: 'SP500',
    currency: 'USD',
    name: 'Apple',
    code: 'AAPL',
    price: 197.26,
    position_pct: 36,
    rsi: 42,
    disparity: 98.6,
    buy_target: 192.4,
    sell_target: 209.8,
    stop_loss: 186.5,
    frgn_net: 0,
    inst_net: 0,
    pension_net: 0,
    fin_invest_net: 0,
    individual_net: 0,
    is_double_buy: false,
    updatedAt: new Date().toISOString(),
  },
];

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatPrice(price, currency) {
  const value = safeNumber(price);
  if (currency === 'USD') {
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${Math.round(value).toLocaleString('ko-KR')}원`;
}

function formatFlow(value) {
  const n = safeNumber(value);
  const sign = n > 0 ? '+' : '';
  if (Math.abs(n) >= 10000) {
    return `${sign}${Math.round(n / 10000).toLocaleString('ko-KR')}만`;
  }
  return `${sign}${Math.round(n).toLocaleString('ko-KR')}`;
}

function formatCompactPrice(value, currency) {
  const n = safeNumber(value);
  if (currency === 'USD') {
    return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return Math.round(n).toLocaleString('ko-KR');
}

function formatVolume(value) {
  const n = safeNumber(value);
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}억`;
  if (n >= 10000) return `${Math.round(n / 10000).toLocaleString('ko-KR')}만`;
  return Math.round(n).toLocaleString('ko-KR');
}

function formatChange(value, currency) {
  const n = safeNumber(value);
  const sign = n > 0 ? '+' : '';
  if (currency === 'USD') {
    return `${sign}${n.toFixed(2)}`;
  }
  return `${sign}${Math.round(n).toLocaleString('ko-KR')}`;
}

function calcQualityScore(stock) {
  const position = safeNumber(stock.position_pct, 50);
  const rsi = safeNumber(stock.rsi, 50);
  const disparity = Math.abs(safeNumber(stock.disparity, 100) - 100);
  const supply = calcSupplyScore(stock);
  const lowPosition = Math.max(0, 40 - position) * 1.15;
  const calmRsi = Math.max(0, 52 - rsi) * 0.75;
  const trendPenalty = Math.min(disparity * 1.1, 18);
  return Math.max(0, Math.min(100, Math.round(40 + lowPosition + calmRsi + supply * 0.4 - trendPenalty)));
}

function calcSupplyScore(stock) {
  const foreign = safeNumber(stock.frgn_net);
  const institution = safeNumber(stock.inst_net);
  const pension = safeNumber(stock.pension_net);
  const finance = safeNumber(stock.fin_invest_net);
  const individual = safeNumber(stock.individual_net);
  let score = 0;
  if (foreign > 0) score += 22;
  if (institution > 0) score += 22;
  if (pension > 0) score += 14;
  if (finance > 0) score += 8;
  if (individual < 0 && (foreign > 0 || institution > 0)) score += 14;
  if (stock.is_double_buy) score += 20;
  return Math.min(100, score);
}

function hasSupplyData(stock) {
  return [
    stock.frgn_net,
    stock.inst_net,
    stock.pension_net,
    stock.fin_invest_net,
    stock.individual_net,
  ].some((value) => safeNumber(value) !== 0) || Boolean(stock.is_double_buy);
}

function getSignal(stock) {
  const quality = calcQualityScore(stock);
  const supply = calcSupplyScore(stock);
  const position = safeNumber(stock.position_pct, 50);
  const rsi = safeNumber(stock.rsi, 50);
  if (quality >= 72 && supply >= 50 && position <= 40) {
    return { label: '검증 후보', tone: 'buy', text: '조건검색 통과 후 추적' };
  }
  if (supply >= 55) {
    return { label: '수급 관찰', tone: 'watch', text: '외국인/기관 유입 확인' };
  }
  if (position <= 35 && rsi <= 40) {
    return { label: '저점 관찰', tone: 'low', text: '반등 확인 필요' };
  }
  return { label: '대기', tone: 'neutral', text: '추가 확인 전 보류' };
}

function normalizeStock(stock) {
  const quality = calcQualityScore(stock);
  const supply = calcSupplyScore(stock);
  const signal = getSignal(stock);
  const rewardPct = stock.price ? ((safeNumber(stock.sell_target) - safeNumber(stock.price)) / safeNumber(stock.price)) * 100 : 0;
  const riskPct = stock.price ? ((safeNumber(stock.price) - safeNumber(stock.stop_loss)) / safeNumber(stock.price)) * 100 : 0;
  const supplyAvailable = hasSupplyData(stock);
  return {
    ...stock,
    quality,
    supply,
    supplyAvailable,
    signal,
    rewardPct,
    riskPct,
    rr: riskPct > 0 ? rewardPct / riskPct : 0,
  };
}

function FlowBadge({ label, value, missing }) {
  const n = safeNumber(value);
  const tone = n > 0 ? 'positive' : n < 0 ? 'negative' : 'flat';
  return (
    <span className={`flow-badge ${tone}`}>
      <span>{label}</span>
      <strong>{missing ? '미수집' : formatFlow(n)}</strong>
    </span>
  );
}

function Metric({ label, value, helper }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {helper && <small>{helper}</small>}
    </div>
  );
}

function SignalPill({ signal }) {
  return <span className={`signal-pill ${signal.tone}`}>{signal.label}</span>;
}

function DataState({ available }) {
  return (
    <span className={`data-state ${available ? 'ready' : 'missing'}`}>
      {available ? '수급 반영' : '수급 미수집'}
    </span>
  );
}

function CandleChart({ points, currency }) {
  if (!points.length) {
    return <div className="chart-empty">차트 데이터를 불러올 수 없습니다.</div>;
  }

  const candles = points.slice(-90);
  const width = 760;
  const height = 360;
  const left = 56;
  const right = 18;
  const top = 18;
  const priceHeight = 238;
  const volumeTop = 280;
  const volumeHeight = 58;
  const plotWidth = width - left - right;
  const lows = candles.map((point) => safeNumber(point.low));
  const highs = candles.map((point) => safeNumber(point.high));
  const volumes = candles.map((point) => safeNumber(point.volume));
  const minPrice = Math.min(...lows);
  const maxPrice = Math.max(...highs);
  const pricePadding = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.01);
  const yMin = minPrice - pricePadding;
  const yMax = maxPrice + pricePadding;
  const yRange = yMax - yMin || 1;
  const maxVolume = Math.max(...volumes, 1);
  const xStep = plotWidth / Math.max(candles.length, 1);
  const candleWidth = Math.max(3, Math.min(10, xStep * 0.58));
  const y = (price) => top + ((yMax - price) / yRange) * priceHeight;
  const volumeY = (volume) => volumeTop + volumeHeight - (volume / maxVolume) * volumeHeight;
  const grid = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const price = yMax - yRange * ratio;
    return { y: top + priceHeight * ratio, price };
  });

  return (
    <svg className="candle-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="일봉 캔들 차트">
      <rect x="0" y="0" width={width} height={height} className="chart-bg" />
      {grid.map((line) => (
        <g key={line.y}>
          <line x1={left} x2={width - right} y1={line.y} y2={line.y} className="chart-grid" />
          <text x={8} y={line.y + 4} className="chart-axis">
            {formatCompactPrice(line.price, currency)}
          </text>
        </g>
      ))}
      {candles.map((point, index) => {
        const x = left + index * xStep + xStep / 2;
        const open = safeNumber(point.open);
        const close = safeNumber(point.close);
        const high = safeNumber(point.high);
        const low = safeNumber(point.low);
        const rising = close >= open;
        const bodyTop = y(Math.max(open, close));
        const bodyHeight = Math.max(2, Math.abs(y(open) - y(close)));
        const volumeHeightValue = volumeTop + volumeHeight - volumeY(point.volume);
        return (
          <g key={`${point.date}-${index}`} className={rising ? 'candle up' : 'candle down'}>
            <line x1={x} x2={x} y1={y(high)} y2={y(low)} />
            <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} rx="1" />
            <rect
              className="volume-bar"
              x={x - candleWidth / 2}
              y={volumeY(point.volume)}
              width={candleWidth}
              height={Math.max(1, volumeHeightValue)}
              rx="1"
            />
          </g>
        );
      })}
      <line x1={left} x2={width - right} y1={volumeTop - 10} y2={volumeTop - 10} className="chart-divider" />
      {candles.length > 1 && (
        <>
          <text x={left} y={352} className="chart-axis">
            {candles[0].date.slice(5)}
          </text>
          <text x={width - right - 44} y={352} className="chart-axis">
            {candles[candles.length - 1].date.slice(5)}
          </text>
        </>
      )}
    </svg>
  );
}

function ChartPanel({ stock, chartData, loading, error, range, onRangeChange }) {
  const points = chartData?.points ?? [];
  const last = points.at(-1);
  const previous = points.at(-2);
  const currency = chartData?.currency ?? stock.currency;
  const change = last && previous ? safeNumber(last.close) - safeNumber(previous.close) : 0;
  const changeRate = last && previous && previous.close ? (change / previous.close) * 100 : 0;
  const tone = change > 0 ? 'up' : change < 0 ? 'down' : 'flat';

  return (
    <div className="chart-section hts-chart-panel">
      <div className="section-title chart-title">
        <div>
          <h3>일봉 차트</h3>
          <span>{chartData?.symbol ?? `${stock.market}:${stock.code}`}</span>
        </div>
        <div className="range-tabs">
          {CHART_RANGES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={range === item.key ? 'active' : ''}
              onClick={() => onRangeChange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="quote-strip">
        <span>
          <small>종가</small>
          <strong>{last ? formatPrice(last.close, currency) : '-'}</strong>
        </span>
        <span className={tone}>
          <small>전일대비</small>
          <strong>
            {formatChange(change, currency)} / {changeRate.toFixed(2)}%
          </strong>
        </span>
        <span>
          <small>고가</small>
          <strong>{last ? formatPrice(last.high, currency) : '-'}</strong>
        </span>
        <span>
          <small>저가</small>
          <strong>{last ? formatPrice(last.low, currency) : '-'}</strong>
        </span>
        <span>
          <small>거래량</small>
          <strong>{last ? formatVolume(last.volume) : '-'}</strong>
        </span>
      </div>

      <div className="chart-canvas">
        {loading ? <div className="chart-empty">차트 로딩 중</div> : <CandleChart points={points} currency={currency} />}
        {!loading && error && <div className="chart-warning">{error}</div>}
      </div>
    </div>
  );
}

function App() {
  const [market, setMarket] = useState('KOSPI');
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('quality');
  const [selectedCode, setSelectedCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [usingSample, setUsingSample] = useState(false);
  const [error, setError] = useState('');
  const [chartRange, setChartRange] = useState('6mo');
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState('');

  const fetchStocks = async (selectedMarket) => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${API_URL}/stocks?market=${selectedMarket}&limit=200`, { timeout: 2500 });
      const rows = Array.isArray(res.data?.data) ? res.data.data : [];
      if (!rows.length) {
        throw new Error('empty response');
      }
      setStocks(rows.map(normalizeStock).sort((a, b) => b.quality - a.quality));
      setUsingSample(false);
    } catch (err) {
      console.error(err);
      const fallback = SAMPLE_STOCKS.filter((stock) => stock.market === selectedMarket).map(normalizeStock);
      setStocks(fallback.sort((a, b) => b.quality - a.quality));
      setUsingSample(true);
      setError('API 연결 전이라 샘플 데이터로 화면을 표시합니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSelectedCode('');
    fetchStocks(market);
  }, [market]);

  const filtered = useMemo(() => {
    if (filterMode === 'quality') {
      return stocks.filter((stock) => stock.quality >= 68 || stock.signal.tone === 'buy');
    }
    if (filterMode === 'supply') {
      return stocks.filter((stock) => stock.supplyAvailable && stock.supply >= 45);
    }
    if (filterMode === 'risk') {
      return stocks.filter((stock) => stock.riskPct <= 7 && stock.rr >= 1.2);
    }
    return stocks;
  }, [stocks, filterMode]);

  const selected = useMemo(() => {
    if (!filtered.length) return null;
    return filtered.find((stock) => stock.code === selectedCode) ?? filtered[0];
  }, [filtered, selectedCode]);

  useEffect(() => {
    if (!selected) {
      setChartData(null);
      setChartError('');
      return;
    }

    let cancelled = false;
    const fetchChart = async () => {
      setChartLoading(true);
      setChartError('');
      try {
        const res = await axios.get(`${API_URL}/stocks/chart`, {
          params: { market: selected.market, code: selected.code, range: chartRange },
          timeout: 7000,
        });
        const points = Array.isArray(res.data?.points) ? res.data.points : [];
        if (!cancelled) {
          setChartData({ ...res.data, points });
          if (!points.length) {
            setChartError('차트 데이터가 없습니다.');
          }
        }
      } catch (err) {
        console.error(err);
        if (!cancelled) {
          setChartData(null);
          setChartError('차트 API 연결 실패');
        }
      } finally {
        if (!cancelled) {
          setChartLoading(false);
        }
      }
    };

    fetchChart();

    return () => {
      cancelled = true;
    };
  }, [selected, chartRange]);

  const stats = useMemo(() => {
    const total = stocks.length;
    const qualityCount = stocks.filter((stock) => stock.quality >= 68 || stock.signal.tone === 'buy').length;
    const supplyDataCount = stocks.filter((stock) => stock.supplyAvailable).length;
    const supplyCount = stocks.filter((stock) => stock.supplyAvailable && stock.supply >= 45).length;
    const avgPosition = total ? stocks.reduce((sum, stock) => sum + safeNumber(stock.position_pct), 0) / total : 0;
    return { total, qualityCount, supplyCount, supplyDataCount, avgPosition };
  }, [stocks]);

  const activeMarket = MARKETS.find((item) => item.key === market);
  const latest = selected?.updatedAt ? new Date(selected.updatedAt).toLocaleString('ko-KR') : '확인 필요';

  return (
    <main className="terminal">
      <header className="topbar">
        <div>
          <p className="eyebrow">KIS HTS형 주식 로봇</p>
          <h1>조건검색 수급 대시보드</h1>
        </div>
        <div className="topbar-actions">
          <div className={`connection ${usingSample ? 'sample' : 'live'}`}>
            <span>{usingSample ? '샘플 모드' : 'API 연결'}</span>
            <strong>{activeMarket?.label}</strong>
          </div>
          <button className="refresh-button" type="button" onClick={() => fetchStocks(market)}>
            새로고침
          </button>
        </div>
      </header>

      <section className="control-strip" aria-label="시장 및 필터">
        <div className="segmented">
          {MARKETS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={market === item.key ? 'active' : ''}
              onClick={() => setMarket(item.key)}
            >
              <span>{item.label}</span>
              <small>{item.sub}</small>
            </button>
          ))}
        </div>
        <div className="filter-bar">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={filterMode === item.key ? 'active' : ''}
              onClick={() => setFilterMode(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="notice">{error}</div>}
      {!error && !loading && market === 'KOSPI' && stats.supplyDataCount === 0 && (
        <div className="notice muted">
          가격/조건검색 데이터는 연결됐지만 KIS 투자자 수급 값은 아직 DB에 저장되지 않았습니다. 수집기를 붙이면 수급점수와 수급확인이 채워집니다.
        </div>
      )}

      <section className="metrics-grid" aria-label="시장 요약">
        <Metric label="스캔 종목" value={`${stats.total}개`} helper="현재 화면 기준" />
        <Metric label="매수 후보" value={`${stats.qualityCount}개`} helper="품질점수 68 이상" />
        <Metric label="수급 데이터" value={`${stats.supplyDataCount}개`} helper={`수급 동반 ${stats.supplyCount}개`} />
        <Metric label="평균 위치" value={`${stats.avgPosition.toFixed(1)}%`} helper="52주 박스 내 위치" />
      </section>

      <section className="workspace">
        <div className="table-panel">
          <div className="panel-heading">
            <div>
              <h2>조건검색 후보</h2>
              <p>{loading ? '데이터를 불러오는 중입니다.' : `${filtered.length}개 후보 표시`}</p>
            </div>
            <span className="timestamp">{latest}</span>
          </div>

          <div className="stock-list" role="table" aria-label="조건검색 후보 목록">
            <div className="stock-list-head" role="row">
              <span>종목</span>
              <span>신호</span>
              <span>품질</span>
              <span>수급</span>
              <span>가격 가이드</span>
            </div>
            {loading && <div className="empty-state">로딩 중</div>}
            {!loading && filtered.length === 0 && <div className="empty-state">조건에 맞는 후보가 없습니다.</div>}
            {!loading && filtered.map((stock) => (
              <button
                type="button"
                key={`${stock.market}-${stock.code}`}
                className={`stock-row ${selected?.code === stock.code ? 'selected' : ''}`}
                onClick={() => setSelectedCode(stock.code)}
              >
                <span className="stock-identity">
                  <strong>{stock.name}</strong>
                  <small>{stock.code}</small>
                </span>
                <span>
                  <SignalPill signal={stock.signal} />
                  <small className="row-sub">{stock.signal.text}</small>
                </span>
                <span className="score-cell">
                  <strong>{stock.quality}</strong>
                  <small>pos {safeNumber(stock.position_pct).toFixed(1)} / RSI {safeNumber(stock.rsi).toFixed(1)}</small>
                </span>
                <span className="score-cell">
                  <strong>{stock.supplyAvailable ? stock.supply : '-'}</strong>
                  <small>{stock.supplyAvailable ? (stock.is_double_buy ? '외+기 동반' : '단일 수급') : '수급 미수집'}</small>
                </span>
                <span className="guide-cell">
                  <strong>{formatPrice(stock.price, stock.currency)}</strong>
                  <small>목표 {formatPrice(stock.sell_target, stock.currency)} / 손절 {formatPrice(stock.stop_loss, stock.currency)}</small>
                </span>
              </button>
            ))}
          </div>
        </div>

        <aside className="detail-panel">
          {selected ? (
            <>
              <div className="panel-heading">
                <div>
                  <h2>{selected.name}</h2>
                  <p>{selected.code} · {market}</p>
                </div>
                <SignalPill signal={selected.signal} />
              </div>

              <div className="price-board">
                <span>현재가</span>
                <strong>{formatPrice(selected.price, selected.currency)}</strong>
                <small>목표까지 {selected.rewardPct.toFixed(2)}% / 손절폭 {selected.riskPct.toFixed(2)}%</small>
              </div>

              <div className="decision-grid">
                <Metric label="품질점수" value={selected.quality} helper="저점·RSI·이격도·수급 합성" />
                <Metric label="수급점수" value={selected.supplyAvailable ? selected.supply : '-'} helper={selected.supplyAvailable ? 'KIS 투자자 흐름' : 'DB 수급값 없음'} />
                <Metric label="손익비" value={selected.rr.toFixed(2)} helper="목표수익 / 손절위험" />
              </div>

              <ChartPanel
                stock={selected}
                chartData={chartData}
                loading={chartLoading}
                error={chartError}
                range={chartRange}
                onRangeChange={setChartRange}
              />

              <div className="flow-section">
                <div className="section-title">
                  <h3>KIS 수급 확인</h3>
                  <DataState available={selected.supplyAvailable} />
                </div>
                <div className="flow-grid">
                  <FlowBadge label="외국인" value={selected.frgn_net} missing={!selected.supplyAvailable} />
                  <FlowBadge label="기관" value={selected.inst_net} missing={!selected.supplyAvailable} />
                  <FlowBadge label="연기금" value={selected.pension_net} missing={!selected.supplyAvailable} />
                  <FlowBadge label="금융투자" value={selected.fin_invest_net} missing={!selected.supplyAvailable} />
                  <FlowBadge label="개인" value={selected.individual_net} missing={!selected.supplyAvailable} />
                </div>
              </div>

              <div className="plan-section">
                <h3>검증 시나리오</h3>
                <ul>
                  <li>다음 거래일 시가 진입 기준 1일, 3일, 7일 성과 저장</li>
                  <li>목표가, 손절가, 장중 최대상승, 최대하락을 분리 기록</li>
                  <li>외국인·기관 동반 순매수와 개인 순매도 조합을 별도 태깅</li>
                </ul>
              </div>
            </>
          ) : (
            <div className="empty-state">후보를 선택하면 상세 검증 기준을 표시합니다.</div>
          )}
        </aside>
      </section>

      <section className="strategy-grid">
        <div className="strategy-panel">
          <h2>서버에 붙일 기능</h2>
          <p>KIS 키를 서버 환경변수에 넣으면 현재 MongoDB 구조를 유지하면서 수급 데이터를 공식 API 기준으로 교체할 수 있습니다.</p>
          <div className="check-list">
            <span>조건검색 후보 저장</span>
            <span>외국인·기관·개인 순매수</span>
            <span>프로그램 매매 보강</span>
            <span>1일·3일·7일 성과 추적</span>
          </div>
        </div>
        <div className="strategy-panel">
          <h2>수익검증에 쓸 기능</h2>
          <p>지금 화면의 신호는 매수 버튼이 아니라 후보 등급입니다. 실제 수익 검증은 닫힌 표본이 쌓인 뒤 승률과 손익비로 판단해야 합니다.</p>
          <div className="check-list">
            <span>다음날 갭 상승/하락</span>
            <span>장중 목표 터치율</span>
            <span>손절 터치율</span>
            <span>수급 조합별 PF</span>
          </div>
        </div>
      </section>
    </main>
  );
}

export default App;
