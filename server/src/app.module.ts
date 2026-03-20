import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { StocksModule } from './stocks/stocks.module';

@Module({
  imports: [
    MongooseModule.forRoot(
      // .net/ 뒤에 StockAnalysis를 추가합니다.
      'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority&appName=Cluster0',
    ),
    StocksModule,
  ],
})
export class AppModule {}
