import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Stock } from './stock.schema';

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
      this.stockModel.find(filter).sort({ position_pct: 1 }).skip(skip).limit(limit).exec(),
      this.stockModel.countDocuments(filter).exec(),
    ]);
    return { data, total, page, limit };
  }
}
