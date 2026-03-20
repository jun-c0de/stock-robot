import FinanceDataReader as fdr
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import pandas as pd
import os # 환경 변수를 읽기 위해 추가

# [보안 적용] GitHub Actions의 Secrets 혹은 로컬 환경 변수에서 URI를 가져옵니다.
# 환경 변수가 설정되어 있지 않으면 기본 주소를 사용합니다.
mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')

client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_detailed_analysis(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)

        if len(df) < 120: return None # 최소 120일 데이터 필요 (이격도 계산용)

        current_price = int(df['Close'].iloc[-1])
        
        # 1. 무릎 위치 계산 (52주 최고/최저 기준)
        max_52w = int(df['High'].max())
        min_52w = int(df['Low'].min())
        position_pct = round(((current_price - min_52w) / (max_52w - min_52w)) * 100, 2)

        # 2. RSI 계산 (14일 기준)
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        rsi = round(100 - (100 / (1 + rs.iloc[-1])), 2)

        # 3. 120일 이동평균선 및 이격도 계산
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disparity = round((current_price / ma120) * 100, 2)

        return {
            "price": current_price,
            "position_pct": position_pct,
            "rsi": rsi,
            "disparity": disparity
        }
    except Exception as e:
        print(f"❌ {code} 분석 오류: {e}")
        return None

def scan_stocks():
    print("🚀 고도화 스캔 시작 (KOSPI 상위 50)...")
    
    try:
        df_kospi = fdr.StockListing('KOSPI')
        target_stocks = df_kospi.head(50)
        
        # 기존 데이터 초기화 전 연결 확인
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
                    "updatedAt": datetime.now()
                }
                collection.insert_one(stock_data)
                print(f"✅ {name}: 위치 {analysis['position_pct']}% | RSI {analysis['rsi']} | 이격도 {analysis['disparity']}%")
            
            time.sleep(0.05)
        print("🎯 고도화 스캔 완료!")
    except Exception as e:
        print(f"💥 스캔 중 치명적 오류 발생: {e}")

if __name__ == "__main__":
    scan_stocks()