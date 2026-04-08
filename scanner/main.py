import FinanceDataReader as fdr
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import os
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

mongo_uri = os.getenv('MONGO_URI')
if not mongo_uri:
    raise EnvironmentError('MONGO_URI 환경변수가 설정되지 않았습니다.')

try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    client.server_info()  # 연결 확인
    db = client['StockAnalysis']
    collection = db['KneeStocks']
    logger.info('MongoDB 연결 성공')
except Exception as e:
    logger.error(f'MongoDB 연결 실패: {e}')
    raise

def get_weekly_investor_data():
    """pykrx 1.0.45의 모든 가능성 있는 함수명을 시도하여 수급 데이터 로드"""
    investor_map = {}
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")

        ohlcv = stock.get_market_ohlcv(start_date, end_date, "005930")
        valid_days = ohlcv.index.strftime("%Y%m%d").tolist()[-5:]
        logger.info(f'분석 대상 거래일: {valid_days}')

        combined_df = pd.DataFrame()

        possible_func_names = [
            'get_market_net_purchase_of_equities',
            'get_market_net_purchase'
        ]

        for day in valid_days:
            df = None
            for func_name in possible_func_names:
                if hasattr(stock, func_name):
                    target_func = getattr(stock, func_name)
                    try:
                        df = target_func(day, day, "KOSPI")
                        if df is not None and not df.empty:
                            break
                    except Exception as e:
                        logger.warning(f'{func_name} 호출 실패 ({day}): {e}')
                        continue

            if df is not None and not df.empty:
                f_col_list = [c for c in df.columns if '외국인' in c]
                i_col_list = [c for c in df.columns if '기관' in c]
                if not f_col_list or not i_col_list:
                    logger.warning(f'{day}: 외국인/기관 컬럼을 찾을 수 없습니다. columns={list(df.columns)}')
                    continue

                temp_df = df[[f_col_list[0], i_col_list[0]]].copy()
                temp_df.columns = ['외국인', '기관합계']

                if combined_df.empty:
                    combined_df = temp_df
                else:
                    combined_df['외국인'] += temp_df['외국인']
                    combined_df['기관합계'] += temp_df['기관합계']

        if not combined_df.empty:
            for ticker, row in combined_df.iterrows():
                investor_map[ticker] = (int(row['외국인']), int(row['기관합계']))
            logger.info(f'수급 데이터 로드 완료: {len(investor_map)}개 종목')
        else:
            logger.warning('수급 데이터가 비어 있습니다.')

    except Exception as e:
        logger.error(f'수급 데이터 로드 최종 실패: {e}')
    return investor_map

def get_detailed_analysis(code, name, investor_data):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = fdr.DataReader(code, start_date, end_date)
        if df is None or len(df) < 120:
            logger.debug(f'{name}({code}): 데이터 부족 (rows={len(df) if df is not None else 0})')
            return None

        curr = int(df['Close'].iloc[-1])
        hi, lo = int(df['High'].max()), int(df['Low'].min())
        pos = round(((curr - lo) / (hi - lo)) * 100, 2)

        delta = df['Close'].diff()
        u, d = delta.clip(lower=0), -1 * delta.clip(upper=0)
        ru, rd = u.ewm(com=13).mean(), d.ewm(com=13).mean()
        rsi = round(100 - (100 / (1 + (ru / rd).iloc[-1])), 2)

        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        disp = round((curr / ma120) * 100, 2)

        f_buy, i_buy = investor_data.get(code, (0, 0))
        is_double_buy = f_buy > 0 and i_buy > 0

        return {
            "price": curr, "position_pct": pos, "rsi": rsi, "disparity": disp,
            "buy_target": int(lo + (hi - lo) * 0.25), "sell_target": int(lo + (hi - lo) * 0.75),
            "stop_loss": int(lo * 0.97), "frgn_buy": f_buy, "inst_buy": i_buy, "is_double_buy": is_double_buy
        }
    except Exception as e:
        logger.warning(f'{name}({code}) 분석 실패: {e}')
        return None

def scan_stocks():
    logger.info('스캔 시작...')
    investor_data = get_weekly_investor_data()

    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except Exception as e:
        logger.error(f'KOSPI 종목 목록 로드 실패: {e}')
        return

    results = []
    for _, row in stocks_list.iterrows():
        name, code = row['Name'], row['Code']
        res = get_detailed_analysis(code, name, investor_data)
        if res:
            results.append({"name": name, "code": code, **res, "updatedAt": datetime.now()})
            logger.info(f'{name}({code}): 외({res["frgn_buy"]}) 기({res["inst_buy"]}) 반영')

    if not results:
        logger.error('분석 결과가 없습니다. DB 업데이트를 건너뜁니다.')
        return

    # 분석 성공 후에만 기존 데이터 삭제
    collection.delete_many({})
    collection.insert_many(results)
    logger.info(f'스캔 완료: {len(results)}개 종목 저장')

if __name__ == "__main__":
    scan_stocks()
