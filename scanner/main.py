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

def get_weekly_investor_data():
    """pykrx 1.0.45의 모든 가능성 있는 함수명을 시도하여 수급 데이터 로드"""
    investor_map = {}
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
        
        # 실제 거래일 5일 추출
        ohlcv = stock.get_market_ohlcv(start_date, end_date, "005930")
        valid_days = ohlcv.index.strftime("%Y%m%d").tolist()[-5:]
        print(f"📊 분석 대상 거래일: {valid_days}")

        combined_df = pd.DataFrame()
        
        # 1.0.45 버전에서 전 종목 수급을 가져오는 후보 함수들
        possible_func_names = [
            'get_market_net_purchase_of_equities',
            'get_market_net_purchase'
        ]

        for day in valid_days:
            df = None
            for func_name in possible_func_names:
                if hasattr(stock, func_name):
                    # 함수 실행 시도
                    target_func = getattr(stock, func_name)
                    try:
                        # 1.0.45 기준: 시작일, 종료일, 시장구분
                        df = target_func(day, day, "KOSPI")
                        if df is not None and not df.empty:
                            break 
                    except:
                        continue
            
            if df is not None and not df.empty:
                # 외국인/기관 컬럼 찾기 (버전 대응)
                f_col = [c for c in df.columns if '외국인' in c][0]
                i_col = [c for c in df.columns if '기관' in c][0]
                
                temp_df = df[[f_col, i_col]].copy()
                temp_df.columns = ['외국인', '기관합계'] # 컬럼명 통일
                
                if combined_df.empty:
                    combined_df = temp_df
                else:
                    combined_df['외국인'] += temp_df['외국인']
                    combined_df['기관합계'] += temp_df['기관합계']
        
        if not combined_df.empty:
            for ticker, row in combined_df.iterrows():
                investor_map[ticker] = (int(row['외국인']), int(row['기관합계']))
            
    except Exception as e:
        print(f"⚠️ 수급 데이터 로드 최종 실패: {e}")
    return investor_map

def get_detailed_analysis(code, name, investor_data):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        if df is None or len(df) < 120: return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)
        
        # RSI
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 이격도
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        f_buy, i_buy = investor_data.get(code, (0, 0))
        is_double_buy = f_buy > 0 and i_buy > 0

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": is_double_buy
        }
    except: return None

def scan_stocks():
    print("🚀 [수급 로직 긴급 패치] 스캔 가동...")
    investor_data = get_weekly_investor_data()
    
    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except: return

    collection.delete_many({}) 

    for _, row in stocks_list.iterrows():
        name, code = row['Name'], row['Code']
        res = get_detailed_analysis(code, name, investor_data)
        if res:
            collection.insert_one({
                "name": name, "code": code, **res, "updatedAt": datetime.now()
            })
            print(f"✅ {name}({code}): 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영")
        
    print("🎯 주간 수급 동기화 완료!")

if __name__ == "__main__":
    scan_stocks()