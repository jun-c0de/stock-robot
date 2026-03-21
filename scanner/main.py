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
    """pykrx 1.0.45 버전에 최적화된 수급 데이터 로드"""
    investor_map = {}
    try:
        # 주말 대응: 최근 15일 중 실제 거래일 추출
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
        
        # 1. 실제 장이 열렸던 날짜 리스트 (삼성전자 기준)
        ohlcv = stock.get_market_ohlcv(start_date, end_date, "005930")
        valid_days = ohlcv.index.strftime("%Y%m%d").tolist()[-5:]
        
        print(f"📊 분석 대상 거래일: {valid_days}")

        # 2. 각 날짜별로 전 종목 수급 합산
        combined_df = pd.DataFrame()
        for day in valid_days:
            # [수정] 1.0.45 버전에서는 get_market_net_purchase 함수를 사용합니다.
            # 인자: 시작일, 종료일, 시장구분
            df = stock.get_market_net_purchase(day, day, "KOSPI")
            
            if df is not None and not df.empty:
                if combined_df.empty:
                    # 필요한 컬럼만 추출 (버전에 따라 '기관합계' 또는 '기관'일 수 있음)
                    f_col = '외국인'
                    i_col = '기관합계' if '기관합계' in df.columns else '기관'
                    combined_df = df[[f_col, i_col]].copy()
                else:
                    i_col = '기관합계' if '기관합계' in df.columns else '기관'
                    combined_df['외국인'] += df['외국인']
                    combined_df[i_col] += df[i_col]
        
        # 3. 딕셔너리 변환
        if not combined_df.empty:
            i_col = '기관합계' if '기관합계' in combined_df.columns else '기관'
            for ticker, row in combined_df.iterrows():
                investor_map[ticker] = (int(row['외국인']), int(row[i_col]))
            
    except Exception as e:
        print(f"⚠️ 전 종목 수급 로드 실패: {e}")
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
        
        # RSI 계산
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 이격도
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 수급 매칭
        f_buy, i_buy = investor_data.get(code, (0, 0))
        is_double_buy = f_buy > 0 and i_buy > 0

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": is_double_buy
        }
    except: return None

def scan_stocks():
    print("🚀 [수급 로직 최종 패치] 스캔 가동...")
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
        
    print("🎯 주간 수급 동기화가 완벽하게 완료되었습니다!")

if __name__ == "__main__":
    scan_stocks()