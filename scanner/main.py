import FinanceDataReader as fdr
from pykrx import stock  # 이 호출 방식을 유지하면서 아래 함수를 사용합니다.
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
    """최근 거래일 기준 수급 분석 (함수 경로 및 이름 최적화)"""
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        
        # [수정] 가장 범용적이고 에러가 적은 함수로 교체
        # 일자별 수급이 아닌, 특정 기간 내 '종목별' 합계 데이터를 가져옵니다.
        df = stock.get_market_net_purchase_of_equities_by_ticker(start_date, end_date, code)
        
        # 만약 위 함수가 실패한다면 아래 주석 처리된 대안 함수를 시도하게 됩니다.
        # df = stock.get_market_net_purchase(start_date, end_date, code)

        if df.empty:
            return 0, 0, False
            
        # pykrx의 get_market_net_purchase_of_equities_by_ticker 결과는 
        # 해당 종목(code)에 대한 행만 반환하므로 iloc[0]을 사용합니다.
        foreign_net = int(df['외국인'].iloc[0])
        inst_net = int(df['기관합계'].iloc[0])
        is_double_buy = foreign_net > 0 and inst_net > 0
        
        return foreign_net, inst_net, is_double_buy
    except Exception as e:
        # 에러 발생 시 로그 출력 후 0 반환
        print(f"❌ {code} 수급 분석 상세 오류: {e}")
        return 0, 0, False

def get_detailed_analysis(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)

        if len(df) < 120: return None

        current_price = int(df['Close'].iloc[-1])
        max_52w = int(df['High'].max())
        min_52w = int(df['Low'].min())
        
        position_pct = round(((current_price - min_52w) / (max_52w - min_52w)) * 100, 2)
        
        delta = df['Close'].diff()
        up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rsi = round(100 - (100 / (1 + (ema_up / ema_down).iloc[-1])), 2)

        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disparity = round((current_price / ma120) * 100, 2)

        buy_target = int(min_52w + (max_52w - min_52w) * 0.25)
        sell_target = int(min_52w + (max_52w - min_52w) * 0.75)
        stop_loss = int(min_52w * 0.97)

        f_buy, i_buy, d_buy = get_investor_analysis(code)

        return {
            "price": current_price,
            "position_pct": position_pct,
            "rsi": rsi,
            "disparity": disparity,
            "buy_target": buy_target,
            "sell_target": sell_target,
            "stop_loss": stop_loss,
            "frgn_buy": f_buy,
            "inst_buy": i_buy,
            "is_double_buy": d_buy
        }
    except Exception as e:
        print(f"❌ {code} 상세 분석 오류: {e}")
        return None

def scan_stocks():
    print("🚀 수급 데이터 정밀 스캔 시작...")
    # 코스피 종목 리스트 가져오기
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
                "frgn_buy": analysis['frgn_buy'],   
                "inst_buy": analysis['inst_buy'],     
                "is_double_buy": analysis['is_double_buy'], 
                "updatedAt": datetime.now()
            }
            collection.insert_one(stock_data)
            print(f"✅ {name}: 외({analysis['frgn_buy']}) 기({analysis['inst_buy']}) 완료")
        
        time.sleep(0.1) # 서버 부하 방지
    print("🎯 모든 수급 데이터 동기화 완료!")

if __name__ == "__main__":
    scan_stocks()