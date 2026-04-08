import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

@Schema({ collection: 'KneeStocks' })
export class Stock extends Document {
  @Prop({ required: true }) name: string;
  @Prop({ required: true, index: true, unique: true }) code: string;
  @Prop() price: number;
  @Prop({ index: true }) position_pct: number;
  @Prop() rsi: number;
  @Prop() disparity: number;
  @Prop() buy_target: number;
  @Prop() sell_target: number;
  @Prop() stop_loss: number;
  @Prop() frgn_buy: number;
  @Prop() inst_buy: number;
  @Prop({ index: true }) is_double_buy: boolean;
  @Prop() updatedAt: Date;
}

export const StockSchema = SchemaFactory.createForClass(Stock);
