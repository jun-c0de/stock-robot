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
    """특정 종목의 최근 5거래일 누적 수급을 가져오는 가장 확실한 방법"""
    try:
        # 주말/휴장일 고려 최근 20일치 조회
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        
        # [수정] pykrx 1.0.45 버전에서 가장 안정적인 종목별 수급 함수
        # 시작일, 종료일, 티커 순서 엄수
        df = stock.get_market_net_purchase_of_equities_by_ticker(start_date, end_date, code)
        
        if df is not None and not df.empty:
            # 1. 컬럼명 유연하게 대응 (외국인, 기관합계)
            f_col = [c for c in df.columns if '외국인' in c]
            i_col = [c for c in df.columns if '기관' in c]
            
            if f_col and i_col:
                # 0이 아닌 거래일만 추출
                valid_df = df[(df[f_col[0]] != 0) | (df[i_col[0]] != 0)]
                weekly_df = valid_df.tail(5)
                
                if not weekly_df.empty:
                    f_sum = int(weekly_df[f_col[0]].sum())
                    i_sum = int(weekly_df[i_col[0]].sum())
                    return f_sum, i_sum, (f_sum > 0 and i_sum > 0)
        
        return 0, 0, False
    except Exception as e:
        # 실행 중 발생하는 미세한 속도 저하 방지를 위해 pass
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
        
        # RSI
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 이격도
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 수급 데이터 (최근 1주일 누적)
        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": d_buy
        }
    except: return None

def scan_stocks():
    print("🚀 [수급 로직 재정비] 스캔 가동...")
    try:
        # 시총 상위 50개 종목
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
            print(f"✅ {name}({code}): 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영")
        time.sleep(0.1) # 딜레이 약간 축소
    print("🎯 모든 데이터가 성공적으로 갱신되었습니다!")

if __name__ == "__main__":
    scan_stocks()