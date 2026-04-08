import FinanceDataReader as fdr
import yfinance as yf
from pykrx import stock
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
import logging
import pandas as pd
import numpy as np

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
    client.server_info()
    db = client['StockAnalysis']
    collection = db['KneeStocks']
    logger.info('MongoDB 연결 성공')
except Exception as e:
    logger.error(f'MongoDB 연결 실패: {e}')
    raise

# ─── 공통 지표 계산 ────────────────────────────────────────────────

def calc_indicators(df_close, df_high, df_low):
    """position_pct, RSI, disparity, 가격 타겟 계산. 데이터 부족 시 None 반환."""
    if df_close is None or len(df_close) < 120:
        return None

    curr = float(df_close.iloc[-1])
    hi = float(df_high.max())
    lo = float(df_low.min())
    if hi == lo:
        return None

    pos = round(((curr - lo) / (hi - lo)) * 100, 2)

    delta = df_close.diff()
    u = delta.clip(lower=0)
    d = -1 * delta.clip(upper=0)
    rsi_val = 100 - (100 / (1 + (u.ewm(com=13).mean() / d.ewm(com=13).mean()).iloc[-1]))
    rsi = round(float(rsi_val), 2)

    ma120 = float(df_close.rolling(window=120).mean().iloc[-1])
    disp = round((curr / ma120) * 100, 2)

    return {
        "price": curr,
        "position_pct": pos,
        "rsi": rsi,
        "disparity": disp,
        "buy_target": lo + (hi - lo) * 0.25,
        "sell_target": lo + (hi - lo) * 0.75,
        "stop_loss": lo * 0.97,
    }

# ─── 한국 수급 ─────────────────────────────────────────────────────

def get_kr_investor_data():
    """pykrx로 KOSPI 5 거래일 수급 데이터 (외국인/기관합계/연기금/금융투자/개인) 로드."""
    investor_map = {}
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")

        ohlcv = stock.get_market_ohlcv(start_date, end_date, "005930")
        valid_days = ohlcv.index.strftime("%Y%m%d").tolist()[-5:]
        logger.info(f'한국 분석 거래일: {valid_days}')

        accum = {}  # ticker → dict of nets

        for day in valid_days:
            try:
                # 전 종목 수급 (투자자별 순매수 금액)
                df = stock.get_market_trading_value_by_investor(day, day, "KOSPI")
                if df is None or df.empty:
                    continue

                # 행 인덱스 = 투자자 구분, 컬럼 = 매도/매수/순매수 등
                # transpose해서 컬럼=투자자, 행=거래구분으로 만들기
                # pykrx 반환 형태: 행=투자자유형, 열=['매도','매수','순매수'] 등
                # 종목별이 아니라 시장 전체 → 종목별로 다시 조회 필요 없음
                # 이미 ticker별 함수 사용
                pass
            except Exception as e:
                logger.warning(f'수급 로드 실패 ({day}): {e}')

        # 종목별 투자자 데이터 조회
        end_date2 = datetime.now().strftime("%Y%m%d")
        start_date2 = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")

        try:
            # 전체 KOSPI 종목 리스트
            kospi_tickers = fdr.StockListing('KOSPI').head(50)['Code'].tolist()
        except Exception as e:
            logger.error(f'KOSPI 종목 목록 로드 실패: {e}')
            return investor_map

        for ticker in kospi_tickers:
            try:
                df = stock.get_market_trading_value_by_investor(start_date2, end_date2, ticker)
                if df is None or df.empty:
                    continue

                def find_col(keywords):
                    for col in df.columns:
                        if any(k in col for k in keywords):
                            return col
                    return None

                net_col = find_col(['순매수'])
                if net_col is None:
                    continue

                def get_net(row_keywords):
                    for idx in df.index:
                        if any(k in str(idx) for k in row_keywords):
                            return int(df.loc[idx, net_col])
                    return 0

                investor_map[ticker] = {
                    'frgn_net':       get_net(['외국인']),
                    'inst_net':       get_net(['기관합계', '기관']),
                    'pension_net':    get_net(['연기금']),
                    'fin_invest_net': get_net(['금융투자']),
                    'individual_net': get_net(['개인']),
                }
            except Exception as e:
                logger.debug(f'{ticker} 수급 조회 실패: {e}')

        logger.info(f'한국 수급 데이터 로드 완료: {len(investor_map)}개')
    except Exception as e:
        logger.error(f'한국 수급 데이터 로드 최종 실패: {e}')

    return investor_map

# ─── 한국 스캔 ─────────────────────────────────────────────────────

def scan_kospi():
    logger.info('=== KOSPI 스캔 시작 ===')
    investor_data = get_kr_investor_data()

    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except Exception as e:
        logger.error(f'KOSPI 종목 목록 로드 실패: {e}')
        return

    results = []
    for _, row in stocks_list.iterrows():
        name, code = row['Name'], row['Code']
        try:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=365)
            df = fdr.DataReader(code, start_dt, end_dt)
            if df is None or len(df) < 120:
                continue

            ind = calc_indicators(df['Close'], df['High'], df['Low'])
            if ind is None:
                continue

            inv = investor_data.get(code, {
                'frgn_net': 0, 'inst_net': 0, 'pension_net': 0,
                'fin_invest_net': 0, 'individual_net': 0
            })
            is_double_buy = inv['frgn_net'] > 0 and inv['inst_net'] > 0

            results.append({
                "market": "KOSPI",
                "currency": "KRW",
                "name": name,
                "code": code,
                **{k: int(v) if k in ('price', 'buy_target', 'sell_target', 'stop_loss') else v
                   for k, v in ind.items()},
                **inv,
                "is_double_buy": is_double_buy,
                "updatedAt": datetime.now(),
            })
            logger.info(f'{name}({code}): 외({inv["frgn_net"]}) 기({inv["inst_net"]}) 연({inv["pension_net"]})')
        except Exception as e:
            logger.warning(f'{name}({code}) 분석 실패: {e}')

    if not results:
        logger.error('KOSPI 분석 결과 없음. DB 업데이트 건너뜀.')
        return

    collection.delete_many({'market': 'KOSPI'})
    collection.insert_many(results)
    logger.info(f'KOSPI 완료: {len(results)}개 저장')

# ─── 미국 스캔 ─────────────────────────────────────────────────────

def scan_sp500():
    logger.info('=== S&P500 스캔 시작 ===')

    try:
        sp500_list = fdr.StockListing('S&P500').head(50)
    except Exception as e:
        logger.error(f'S&P500 종목 목록 로드 실패: {e}')
        return

    results = []
    for _, row in sp500_list.iterrows():
        ticker = row.get('Symbol') or row.get('Code') or row.get('Ticker')
        name = row.get('Name') or ticker
        if not ticker:
            continue
        try:
            df = yf.Ticker(ticker).history(period='1y')
            if df is None or len(df) < 120:
                continue

            ind = calc_indicators(df['Close'], df['High'], df['Low'])
            if ind is None:
                continue

            results.append({
                "market": "SP500",
                "currency": "USD",
                "name": name,
                "code": ticker,
                **{k: round(v, 2) if k in ('price', 'buy_target', 'sell_target', 'stop_loss') else v
                   for k, v in ind.items()},
                "frgn_net": 0, "inst_net": 0, "pension_net": 0,
                "fin_invest_net": 0, "individual_net": 0,
                "is_double_buy": False,
                "updatedAt": datetime.now(),
            })
            logger.info(f'{name}({ticker}): pos={ind["position_pct"]}% rsi={ind["rsi"]}')
        except Exception as e:
            logger.warning(f'{name}({ticker}) 분석 실패: {e}')

    if not results:
        logger.error('S&P500 분석 결과 없음. DB 업데이트 건너뜀.')
        return

    collection.delete_many({'market': 'SP500'})
    collection.insert_many(results)
    logger.info(f'S&P500 완료: {len(results)}개 저장')

# ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scan_kospi()
    scan_sp500()
