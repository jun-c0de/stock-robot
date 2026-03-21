import FinanceDataReader as fdr
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import os

# [보안] 환경 변수 처리
mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://admin:admin1234@cluster0.p49t9un.mongodb.net/StockAnalysis?retryWrites=true&w=majority')
client = MongoClient(mongo_uri)
db = client['StockAnalysis']
collection = db['KneeStocks']

def get_investor_analysis(code):
    """라이브러리 버전에 상관없이 수급 함수를 찾아 실행하는 로직 (안정성 강화)"""
    try:
        # 주말이나 공휴일을 대비해 분석 기간을 넉넉히 잡음
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        
        target_func = None
        # pykrx의 다양한 함수명 후보군
        possible_names = [
            'get_market_net_purchase_of_equities_by_ticker',
            'get_market_net_purchase_by_ticker',
            'get_market_net_purchase'
        ]
        
        # 1. 속성 존재 여부 확인 후 함수 할당
        for name in possible_names:
            if hasattr(stock, name):
                target_func = getattr(stock, name)
                break
        
        if target_func:
            # 2. 데이터 가져오기 (인자 순서: 시작일, 종료일, 종목코드)
            df = target_func(start_date, end_date, code)
            
            if df is not None and not df.empty:
                # 3. 컬럼명 유연하게 대응 (버전에 따라 다를 수 있음)
                f_col = '외국인' if '외국인' in df.columns else None
                i_col = '기관합계' if '기관합계' in df.columns else None
                
                if f_col and i_col:
                    f_val = int(df[f_col].iloc[-1])
                    i_val = int(df[i_col].iloc[-1])
                    return f_val, i_val, (f_val > 0 and i_val > 0)
        
        return 0, 0, False
    except Exception as e:
        # 에러 발생 시 로그에 상세 이유 출력 (디버깅용)
        print(f"⚠️ {code} 수급 분석 오류: {str(e)}")
        return 0, 0, False

def get_detailed_analysis(code):
    try:
        # 최근 1년치 데이터로 위치 및 RSI 계산
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        
        if df is None or len(df) < 120: return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        
        # 52주 위치 (%)
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)
        
        # RSI (상대강도지수) 계산
        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)
        
        # 이격도 (120일선 기준)
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        # 수급 데이터 연동
        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25),
            "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97),
            "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": d_buy
        }
    except Exception:
        return None

def scan_stocks():
    print("🚀 [최종 점검] 수급 데이터 정밀 스캔 가동...")
    # 시총 상위 50개 종목 우선 스캔
    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except:
        print("❌ 종목 리스트 로드 실패")
        return

    collection.delete_many({}) # 기존 데이터 초기화

    for _, row in stocks_list.iterrows():
        name = row['Name']
        code = row['Code']
        res = get_detailed_analysis(code)
        
        if res:
            collection.insert_one({
                "name": name, "code": code, **res, "updatedAt": datetime.now()
            })
            # 로그에 실제 숫자가 찍히는지 확인하는 핵심 포인트
            print(f"✅ {name}({code}): 외({res['frgn_buy']}) 기({res['inst_buy']}) 반영 완료")
        
        time.sleep(0.2) # API 차단 방지용 딜레이
    print("🎯 모든 데이터가 성공적으로 갱신되었습니다.")

if __name__ == "__main__":
    scan_stocks()