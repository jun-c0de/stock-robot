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
    """최근 거래일 기준 수급 분석 (함수명 수정 및 주말 대응)"""
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        
        # [수정] 정확한 함수명: get_market_net_purchase_by_ticker
        df = stock.get_market_net_purchase_by_ticker(start_date, end_date, code)
        
        if df.empty:
            return 0, 0, False
            
        # 가장 최근 거래일(-1) 데이터 추출
        foreign_net = int(df['외국인'].iloc[-1])
        inst_net = int(df['기관합계'].iloc[-1])
        is_double_buy = foreign_net > 0 and inst_net > 0
        
        return foreign_net, inst_net, is_double_buy
    except Exception as e:
        print(f"❌ {code} 수급 분석 오류: {e}")
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
    print("🎯 모든 갱신 완료!")

if __name__ == "__main__":
    scan_stocks()