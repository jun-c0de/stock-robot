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

  // --- 수급 데이터 필드 추가 ---
  @Prop() frgn_buy: number; // 외국인 순매수량
  @Prop() inst_buy: number; // 기관 순매수량
  @Prop() is_double_buy: boolean; // 쌍끌이 매수 여부
  // -----------------------

  @Prop() updatedAt: Date;
}

export const StockSchema = SchemaFactory.createForClass(Stock);
