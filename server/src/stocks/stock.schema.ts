import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

@Schema({ collection: 'KneeStocks' })
export class Stock extends Document {
  @Prop() name: string;
  @Prop() code: string;
  @Prop() price: number;
  @Prop() position_pct: number;
  @Prop() rsi: number;      // 추가
  @Prop() disparity: number; // 추가
  @Prop() updatedAt: Date;
}

export const StockSchema = SchemaFactory.createForClass(Stock);