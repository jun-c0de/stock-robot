import FinanceDataReader as fdr
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import pandas as pd
import os

# [보안] 환경 변수에서 URI를 가져오고, 없으면 기본값 사용
mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')

client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_detailed_analysis(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)

        if len(df) < 120: return None

        current_price = int(df['Close'].iloc[-1])
        max_52w = int(df['High'].max())
        min_52w = int(df['Low'].min())
        
        # 1. 무릎 위치 계산
        position_pct = round(((current_price - min_52w) / (max_52w - min_52w)) * 100, 2)

        # 2. RSI 계산 (14일)
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        rsi = round(100 - (100 / (1 + rs.iloc[-1])), 2)

        # 3. 120일 이격도 계산
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disparity = round((current_price / ma120) * 100, 2)

        # 4. 뇌동매매 방지 가격 가이드 (25% 매수, 75% 매도, 최저가 -3% 손절)
        buy_target = int(min_52w + (max_52w - min_52w) * 0.25)
        sell_target = int(min_52w + (max_52w - min_52w) * 0.75)
        stop_loss = int(min_52w * 0.97)

        return {
            "price": current_price,
            "position_pct": position_pct,
            "rsi": rsi,
            "disparity": disparity,
            "buy_target": buy_target,
            "sell_target": sell_target,
            "stop_loss": stop_loss
        }
    except Exception as e:
        print(f"❌ {code} 분석 오류: {e}")
        return None

def scan_stocks():
    print("🚀 뇌동매매 방지 스캐너 가동 (KOSPI 50)...")
    df_kospi = fdr.StockListing('KOSPI')
    target_stocks = df_kospi.head(50)
    
    collection.delete_many({})

    for index, row in target_stocks.iterrows():
        code = row['Code']
        name = row['Name']
        analysis = get_detailed_analysis(code)
        
        if analysis:
            stock_data = {
                "name": name,
                "code": code,
                "price": analysis['price'],
                "position_pct": analysis['position_pct'],
                "rsi": analysis['rsi'],
                "disparity": analysis['disparity'],
                "buy_target": analysis['buy_target'],
                "sell_target": analysis['sell_target'],
                "stop_loss": analysis['stop_loss'],
                "updatedAt": datetime.now()
            }
            collection.insert_one(stock_data)
            print(f"✅ {name} 데이터 업데이트 완료")
        
        time.sleep(0.05)
    print("🎯 모든 데이터 갱신 완료!")

if __name__ == "__main__":
    scan_stocks()