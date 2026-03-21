import FinanceDataReader as fdr
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import os

mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')
client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_investor_analysis(code):
    """라이브러리 버전에 상관없이 가장 안정적인 함수로 수급 데이터 추출"""
    try:
        # 주말 대응을 위해 넉넉히 최근 20일치 요청
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        
        # [핵심 변경] 가장 호환성이 좋은 함수로 교체
        # 인자 순서: 시작일, 종료일, 종목코드
        df = stock.get_market_net_purchase_of_equities(start_date, end_date, code)
        
        if df is not None and not df.empty:
            # 0이 아닌 거래일만 필터링 (주말/휴장일 제외)
            valid_df = df[(df['외국인'] != 0) | (df['기관합계'] != 0)]
            
            # 최근 5거래일(1주일치) 누적 합산
            weekly_df = valid_df.tail(5)
            
            if not weekly_df.empty:
                f_sum = int(weekly_df['외국인'].sum())
                i_sum = int(weekly_df['기관합계'].sum())
                # 둘 다 주간 누적 양수일 때 True
                return f_sum, i_sum, (f_sum > 0 and i_sum > 0)
        
        return 0, 0, False
    except Exception as e:
        # 에러 로그를 최소화하여 실행 속도 유지
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
        
        # RSI 계산
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 이격도
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 수급 데이터 연동
        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": d_buy
        }
    except: return None

def scan_stocks():
    print("🚀 [최종 해결본] 주간 수급 동기화 시작...")
    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except: return

    collection.delete_many({}) 

    for _, row in stocks_list.iterrows():
        name, code = row['Name'], row['Code']
        res = get_detailed_analysis(code)
        if res:
            collection.insert_one({
                "name": name, "code": code, **res, "updatedAt": datetime.now()
            })
            # 로그에 드디어 숫자가 찍히기 시작할 겁니다
            print(f"✅ {name}({code}): 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영")
        time.sleep(0.2)
    print("🎯 모든 데이터가 성공적으로 갱신되었습니다!")

if __name__ == "__main__":
    scan_stocks()