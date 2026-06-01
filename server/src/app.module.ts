import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { setServers } from 'node:dns';
import { StocksModule } from './stocks/stocks.module';

if (process.env.MONGODB_DNS_SERVERS) {
  setServers(
    process.env.MONGODB_DNS_SERVERS
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
  );
}

@Module({
  imports: [
    MongooseModule.forRoot(
      process.env.MONGODB_URI ?? '',
      { dbName: process.env.MONGODB_DB ?? 'StockAnalysis' },
    ),
    StocksModule,
  ],
})
export class AppModule {}
