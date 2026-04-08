import FinanceDataReader as fdr
import yfinance as yf
from pykrx import stock
from pymongo import MongoClient, ReplaceOne
from datetime import datetime, timedelta
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
    client.server_info()
    db = client['StockAnalysis']
    collection = db['KneeStocks']
    logger.info('MongoDB 연결 성공')

    # 구버전 code 단독 unique 인덱스 제거 (market+code 복합 인덱스로 대체됨)
    try:
        collection.drop_index('code_1')
        logger.info('구버전 code_1 인덱스 제거 완료')
    except Exception:
        pass  # 이미 없으면 무시

except Exception as e:
    logger.error('MongoDB 연결 실패: %s', e)
    raise

# ─── 공통 지표 계산 ────────────────────────────────────────────────

def calc_indicators(df_close, df_high, df_low):
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
    """
    1단계: get_market_net_purchase_of_equities 로 시장 전체 외국인/기관합계 취득 (기존 동작 방식)
    2단계: 종목별 get_market_trading_value_by_investor 로 연기금/금융투자/개인 추가 시도 (실패 시 0)
    """
    investor_map = {}

    # ── 1단계: 시장 전체 외국인/기관합계 ──────────────────────────
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")

        ohlcv = stock.get_market_ohlcv(start_date, end_date, "005930")
        valid_days = ohlcv.index.strftime("%Y%m%d").tolist()[-5:]
        logger.info('한국 분석 거래일: %s', valid_days)

        combined_df = pd.DataFrame()
        possible_funcs = ['get_market_net_purchase_of_equities', 'get_market_net_purchase']

        for day in valid_days:
            for func_name in possible_funcs:
                if not hasattr(stock, func_name):
                    continue
                try:
                    df = getattr(stock, func_name)(day, day, "KOSPI")
                    if df is None or df.empty:
                        continue
                    f_col = next((c for c in df.columns if '외국인' in c), None)
                    i_col = next((c for c in df.columns if '기관' in c), None)
                    if not f_col or not i_col:
                        continue
                    temp = df[[f_col, i_col]].copy()
                    temp.columns = ['외국인', '기관합계']
                    combined_df = temp if combined_df.empty else combined_df.add(temp, fill_value=0)
                    break
                except Exception as e:
                    logger.debug('%s 호출 실패 (%s): %s', func_name, day, e)

        for ticker, row in combined_df.iterrows():
            investor_map[str(ticker)] = {
                'frgn_net':       int(row['외국인']),
                'inst_net':       int(row['기관합계']),
                'pension_net':    0,
                'fin_invest_net': 0,
                'individual_net': 0,
            }
        logger.info('1단계 수급 완료: %d개 종목', len(investor_map))

    except Exception as e:
        logger.error('1단계 수급 로드 실패: %s', e)

    # ── 2단계: 종목별 상세 수급 (연기금/금융투자/개인) ───────────
    try:
        period_end = datetime.now().strftime("%Y%m%d")
        period_start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        tickers = list(investor_map.keys())

        for ticker in tickers:
            try:
                df = stock.get_market_trading_value_by_investor(period_start, period_end, ticker)
                if df is None or df.empty:
                    continue
                net_col = next((c for c in df.columns if '순매수' in c), None)
                if net_col is None:
                    continue

                def get_row(keywords):
                    for idx in df.index:
                        if any(k in str(idx) for k in keywords):
                            return int(df.loc[idx, net_col])
                    return 0

                investor_map[ticker].update({
                    'frgn_net':       get_row(['외국인']),
                    'inst_net':       get_row(['기관합계', '기관']),
                    'pension_net':    get_row(['연기금']),
                    'fin_invest_net': get_row(['금융투자']),
                    'individual_net': get_row(['개인']),
                })
            except Exception:
                pass  # 실패 시 1단계 값 그대로 유지

        logger.info('2단계 수급 완료')
    except Exception as e:
        logger.warning('2단계 수급 로드 실패 (계속 진행): %s', e)

    return investor_map

# ─── 한국 스캔 ─────────────────────────────────────────────────────

def scan_kospi():
    logger.info('=== KOSPI 스캔 시작 ===')
    investor_data = get_kr_investor_data()

    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except Exception as e:
        logger.error('KOSPI 종목 목록 로드 실패: %s', e)
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
                "price": int(ind["price"]),
                "position_pct": ind["position_pct"],
                "rsi": ind["rsi"],
                "disparity": ind["disparity"],
                "buy_target": int(ind["buy_target"]),
                "sell_target": int(ind["sell_target"]),
                "stop_loss": int(ind["stop_loss"]),
                **inv,
                "is_double_buy": is_double_buy,
                "updatedAt": datetime.now(),
            })
            logger.info('%s(%s): 외(%d) 기(%d) 연(%d)', name, code,
                        inv['frgn_net'], inv['inst_net'], inv['pension_net'])
        except Exception as e:
            logger.warning('%s(%s) 분석 실패: %s', name, code, e)

    if not results:
        logger.error('KOSPI 분석 결과 없음. DB 업데이트 건너뜀.')
        return

    ops = [ReplaceOne({'market': r['market'], 'code': r['code']}, r, upsert=True) for r in results]
    collection.bulk_write(ops, ordered=False)
    logger.info('KOSPI 완료: %d개 저장', len(results))

# ─── 미국 스캔 ─────────────────────────────────────────────────────

def scan_sp500():
    logger.info('=== S&P500 스캔 시작 ===')

    try:
        sp500_list = fdr.StockListing('S&P500').head(50)
    except Exception as e:
        logger.error('S&P500 종목 목록 로드 실패: %s', e)
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
                "price": round(ind["price"], 2),
                "position_pct": ind["position_pct"],
                "rsi": ind["rsi"],
                "disparity": ind["disparity"],
                "buy_target": round(ind["buy_target"], 2),
                "sell_target": round(ind["sell_target"], 2),
                "stop_loss": round(ind["stop_loss"], 2),
                "frgn_net": 0, "inst_net": 0, "pension_net": 0,
                "fin_invest_net": 0, "individual_net": 0,
                "is_double_buy": False,
                "updatedAt": datetime.now(),
            })
            logger.info('%s(%s): pos=%.1f%% rsi=%.1f', name, ticker,
                        ind["position_pct"], ind["rsi"])
        except Exception as e:
            logger.warning('%s(%s) 분석 실패: %s', name, ticker, e)

    if not results:
        logger.error('S&P500 분석 결과 없음. DB 업데이트 건너뜀.')
        return

    ops = [ReplaceOne({'market': r['market'], 'code': r['code']}, r, upsert=True) for r in results]
    collection.bulk_write(ops, ordered=False)
    logger.info('S&P500 완료: %d개 저장', len(results))

# ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scan_kospi()
    scan_sp500()
