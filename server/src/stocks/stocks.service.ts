import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { Stock } from './stock.schema'; // 스키마 파일 이름 확인 (stock.schema)

@Injectable()
export class StocksService {
  constructor(@InjectModel(Stock.name) private stockModel: Model<Stock>) {}

  async findAll(): Promise<Stock[]> {
    return await this.stockModel.find().sort({ position_pct: 1 }).exec();
  }
}
