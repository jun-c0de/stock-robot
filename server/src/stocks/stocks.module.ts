import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { StocksController } from './stocks.controller'; // 👈 추가 확인
import { StocksService } from './stocks.service';
import { Stock, StockSchema } from './stock.schema';

@Module({
  imports: [
    MongooseModule.forFeature([{ name: Stock.name, schema: StockSchema }]),
  ],
  controllers: [StocksController], // 👈 여기에 StocksController가 포함되어 있나요?
  providers: [StocksService],
})
export class StocksModule {}
