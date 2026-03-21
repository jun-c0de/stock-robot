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
    """최근 거래일 기준 수급 분석 (주말/공휴일 대응 완료)"""
    try:
        # 종료일은 오늘, 시작일은 10일 전으로 설정하여 주말/공휴일 공백을 메움
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        
        # 기간 내의 일자별 순매수량 데이터 가져오기
        df = stock.get_market_net_purchase_of_equities_by_ticker(start_date, end_date, code)
        
        if df.empty:
            print(f"⚠️ {code}: 수급 데이터가 비어있음")
            return 0, 0, False
            
        # [핵심] iloc[-1]을 사용하여 해당 기간 중 '가장 최근 거래일' 데이터를 추출
        foreign_net = int(df['외국인'].iloc[-1])
        inst_net = int(df['기관합계'].iloc[-1])
        
        # 쌍끌이 매수 여부
        is_double_buy = foreign_net > 0 and inst_net > 0
        
        return foreign_net, inst_net, is_double_buy
    except Exception as e:
        print(f"❌ 수급 분석 오류 ({code}): {e}")
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

        # 수급 데이터 필드명 동기화 (frgn_buy, inst_buy)
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
    print("🚀 실시간 수급 동기화 스캐너 가동...")
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
            print(f"✅ {name}: 외({analysis['frgn_buy']}) 기({analysis['inst_buy']}) 저장 완료")
        
        time.sleep(0.05)
    print("🎯 주말 데이터 보정 포함 모든 갱신 완료!")

if __name__ == "__main__":
    scan_stocks()