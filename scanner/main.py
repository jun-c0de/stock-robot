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
    """실제 거래 데이터가 있는 날을 기준으로 최근 5거래일 누적 수급 분석"""
    try:
        # 주말 및 휴장일을 고려하여 최근 30일치 데이터를 넉넉하게 요청
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        
        target_func = None
        # pykrx의 표준 함수명 리스트 (버전 대응)
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
                # [핵심] 외국인이나 기관 수급이 0이 아닌 '실제 거래일'만 필터링
                # 주말이나 데이터 미반영일이 0으로 들어오는 문제를 원천 차단합니다.
                valid_df = df[(df['외국인'] != 0) | (df['기관합계'] != 0)]
                
                # 유효한 거래일 중 가장 최근 5일(1주일치) 데이터만 선택
                weekly_df = valid_df.tail(5)
                
                if not weekly_df.empty:
                    # 5일간의 순매수량 합계 계산 (네이버 증권 흐름과 일치)
                    f_sum = int(weekly_df['외국인'].sum())
                    i_sum = int(weekly_df['기관합계'].sum())
                    
                    # 외국인과 기관이 1주일 누적 모두 양수일 때 'is_double_buy'를 True로 설정
                    is_double_buy = f_sum > 0 and i_sum > 0
                    
                    return f_sum, i_sum, is_double_buy
        
        return 0, 0, False
    except Exception as e:
        print(f"⚠️ {code} 수급 분석 중 오류 발생: {str(e)}")
        return 0, 0, False

def get_detailed_analysis(code):
    """종목별 가격 위치, RSI, 이격도 및 수급 분석 통합"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        
        if df is None or len(df) < 120: return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        
        # 52주 가격 위치 (%)
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)
        
        # RSI(상대강도지수) 계산
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 120일 이격도 계산
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 1주일 누적 수급 데이터 가져오기
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
    print("🚀 [최종 보강] 주간 누적 수급 스캐너 가동...")
    
    try:
        # KOSPI 시총 상위 50개 종목 리스트업
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except:
        print("❌ KOSPI 종목 리스트 로드 실패")
        return

    # DB 초기화 후 새로운 분석 데이터 삽입
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
            # 로그에 주간 누적 숫자가 정상적으로 찍히는지 확인
            print(f"✅ {name}({code}): 주간 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영 완료")
        
        time.sleep(0.2) # API 차단 방지용 딜레이
        
    print("🎯 모든 데이터가 성공적으로 갱신되었습니다.")

if __name__ == "__main__":
    scan_stocks()