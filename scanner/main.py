import FinanceDataReader as fdr
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import os

# [보안] MongoDB 연결 설정
mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')
client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_investor_analysis(code):
    """최근 1주일(5거래일) 누적 수급 분석 로직"""
    try:
        # 네이버 증권처럼 최근 5거래일 합계를 구하기 위해 기간을 넉넉히(14일) 설정
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
        
        target_func = None
        # pykrx 버전별 가능성 있는 함수명 리스트
        possible_names = [
            'get_market_net_purchase_of_equities_by_ticker',
            'get_market_net_purchase'
        ]
        
        for name in possible_names:
            if hasattr(stock, name):
                target_func = getattr(stock, name)
                break
        
        if target_func:
            df = target_func(start_date, end_date, code)
            
            if df is not None and not df.empty:
                # [핵심] 최근 5거래일(1주일) 데이터만 추출하여 합산
                weekly_df = df.tail(5)
                
                f_col = '외국인' if '외국인' in df.columns else None
                i_col = '기관합계' if '기관합계' in df.columns else None
                
                if f_col and i_col:
                    # 5일간의 순매수량 합계 (네이버 증권 흐름 반영)
                    f_sum = int(weekly_df[f_col].sum())
                    i_sum = int(weekly_df[i_col].sum())
                    
                    # 외국인/기관 모두 1주일 누적 양수일 때 '양매수'로 판단
                    is_double_buy = f_sum > 0 and i_sum > 0
                    
                    return f_sum, i_sum, is_double_buy
        
        return 0, 0, False
    except Exception as e:
        print(f"⚠️ {code} 수급 분석 오류: {str(e)}")
        return 0, 0, False

def get_detailed_analysis(code):
    """기본적/기술적 지표 분석"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        
        if df is None or len(df) < 120: return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        
        # 52주 가격 위치 (%)
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)
        
        # RSI 계산
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 120일 이격도
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 1주일 누적 수급 데이터 연동
        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": curr, 
            "position_pct": pos, 
            "rsi": rsi, 
            "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25),
            "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97),
            "frgn_buy": f_buy, 
            "inst_buy": i_buy, 
            "is_double_buy": d_buy
        }
    except:
        return None

def scan_stocks():
    print("🚀 [주간 수급 분석] KOSPI 상위 종목 정밀 스캔 가동...")
    
    try:
        # 시총 상위 50개 종목 리스트업
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except:
        print("❌ KOSPI 종목 리스트 로드 실패")
        return

    # 기존 데이터 초기화 후 새로 인서트
    collection.delete_many({}) 

    for _, row in stocks_list.iterrows():
        name = row['Name']
        code = row['Code']
        res = get_detailed_analysis(code)
        
        if res:
            collection.insert_one({
                "name": name, 
                "code": code, 
                **res, 
                "updatedAt": datetime.now()
            })
            # 로그에서 주간 합계 숫자가 찍히는지 확인 가능
            print(f"✅ {name}({code}): 주간 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영 완료")
        
        time.sleep(0.2) # API 과부하 방지
        
    print("🎯 모든 주간 수급 데이터 동기화 완료!")

if __name__ == "__main__":
    scan_stocks()