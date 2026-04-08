import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { Document } from 'mongoose';

@Schema({ collection: 'KneeStocks' })
export class Stock extends Document {
  @Prop({ required: true, index: true }) market: string;       // 'KOSPI' | 'SP500'
  @Prop({ default: 'KRW' }) currency: string;                  // 'KRW' | 'USD'
  @Prop({ required: true }) name: string;
  @Prop({ required: true }) code: string;
  @Prop() price: number;
  @Prop({ index: true }) position_pct: number;
  @Prop() rsi: number;
  @Prop() disparity: number;
  @Prop() buy_target: number;
  @Prop() sell_target: number;
  @Prop() stop_loss: number;
  @Prop({ default: 0 }) frgn_net: number;        // 외국인 순매수
  @Prop({ default: 0 }) inst_net: number;          // 기관합계 순매수
  @Prop({ default: 0 }) pension_net: number;       // 연기금 순매수
  @Prop({ default: 0 }) fin_invest_net: number;    // 금융투자 순매수
  @Prop({ default: 0 }) individual_net: number;    // 개인 순매수
  @Prop({ index: true }) is_double_buy: boolean;
  @Prop() updatedAt: Date;
}

export const StockSchema = SchemaFactory.createForClass(Stock);
StockSchema.index({ market: 1, code: 1 }, { unique: true });
