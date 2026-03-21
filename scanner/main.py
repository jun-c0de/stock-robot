import FinanceDataReader as fdr
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import os
import pandas as pd

mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')
client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_investor_analysis(code):
    try:
        # 주말 대응을 위해 넉넉히 20일치 요청
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        
        # 가장 확실한 함수 하나만 집중 공략
        df = stock.get_market_net_purchase_of_equities_by_ticker(start_date, end_date, code)
        
        if df is not None and not df.empty:
            # [디버깅 로그] 삼성전자(005930)일 때만 실제 데이터 구조 출력
            if code == "005930":
                print(f"\n🔍 [DEBUG] 삼성전자 데이터 구조:\n{df.tail(3)}")
                print(f"🔍 [DEBUG] 컬럼명 리스트: {df.columns.tolist()}")

            # 0이 아닌 거래일만 필터링
            # 컬럼명이 '외국인', '기관합계'가 아닐 경우를 대비해 위치(index)로 접근 시도
            # 보통 pykrx 수급 표는 외국인이 6번째, 기관합계가 8번째쯤 있습니다.
            
            # 1. 이름으로 접근 시도
            f_col = '외국인' if '외국인' in df.columns else df.columns[6] if len(df.columns) > 6 else None
            i_col = '기관합계' if '기관합계' in df.columns else df.columns[8] if len(df.columns) > 8 else None

            if f_col and i_col:
                # 데이터가 0인 날 제외
                valid_df = df[(df[f_col] != 0) | (df[i_col] != 0)]
                weekly_df = valid_df.tail(5)
                
                if not weekly_df.empty:
                    f_sum = int(weekly_df[f_col].sum())
                    i_sum = int(weekly_df[i_col].sum())
                    return f_sum, i_sum, (f_sum > 0 and i_sum > 0)
        
        return 0, 0, False
    except Exception as e:
        print(f"⚠️ {code} 분석 중 에러: {e}")
        return 0, 0, False

def get_detailed_analysis(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        if df is None or len(df) < 120: return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)
        
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": d_buy
        }
    except: return None

def scan_stocks():
    print("🚀 [디버깅 모드] 스캔 시작...")
    stocks_list = fdr.StockListing('KOSPI').head(50)
    collection.delete_many({}) 

    for _, row in stocks_list.iterrows():
        res = get_detailed_analysis(row['Code'])
        if res:
            collection.insert_one({
                "name": row['Name'], "code": row['Code'], **res, "updatedAt": datetime.now()
            })
            print(f"✅ {row['Name']}: 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영")
        time.sleep(0.2)
    print("🎯 동기화 완료!")

if __name__ == "__main__":
    scan_stocks()