import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

@Schema({ collection: 'KneeStocks' })
export class Stock extends Document {
  @Prop() name: string;
  @Prop() code: string;
  @Prop() price: number;
  @Prop() position_pct: number;
  @Prop() rsi: number;
  @Prop() disparity: number;
  @Prop() buy_target: number;
  @Prop() sell_target: number;
  @Prop() stop_loss: number;
  @Prop() updatedAt: Date;
}

export const StockSchema = SchemaFactory.createForClass(Stock);
