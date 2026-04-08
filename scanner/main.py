import FinanceDataReader as fdr
import yfinance as yf
from pykrx import stock
from pymongo import MongoClient, ReplaceOne
from datetime import datetime, timedelta
import os
import logging
import requests
from io import StringIO
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

# ─── 한국 수급 (NAVER Finance 스크래핑) ───────────────────────────

NAVER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.naver.com',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}

def _find_net_col(df, keyword):
    """MultiIndex 또는 단일 컬럼에서 keyword + 합계/순매수 컬럼 찾기."""
    candidates = []
    for col in df.columns:
        col_str = str(col)
        if keyword in col_str:
            candidates.append(col)
    # 합계 우선, 없으면 첫 번째
    for col in candidates:
        if '합계' in str(col) or '순매수' in str(col):
            return col
    return candidates[0] if candidates else None

def get_kr_investor_data(tickers):
    """
    NAVER Finance investor.naver 페이지에서 5일 수급 합계 스크래핑.
    (외국인/기관합계/개인 — 연기금/금융투자는 NAVER 미제공으로 0)
    실패 시 0으로 fallback.
    """
    investor_map = {}
    success = 0

    for ticker in tickers:
        try:
            url = f'https://finance.naver.com/item/investor.naver?code={ticker}'
            resp = requests.get(url, headers=NAVER_HEADERS, timeout=10)
            resp.encoding = 'cp949'

            tables = pd.read_html(StringIO(resp.text), flavor='lxml')

            # 개인/외국인 컬럼이 있는 테이블 선택
            target = None
            for t in tables:
                joined = ' '.join(str(c) for c in t.columns.tolist())
                if '개인' in joined and '외국인' in joined:
                    target = t
                    break

            if target is None:
                logger.warning('%s: 수급 테이블 없음', ticker)
                continue

            # MultiIndex 컬럼 → 문자열로 flatten
            if isinstance(target.columns, pd.MultiIndex):
                target.columns = [' '.join(str(x) for x in col if 'Unnamed' not in str(x)).strip()
                                   for col in target.columns]

            frgn_col  = _find_net_col(target, '외국인')
            inst_col  = _find_net_col(target, '기관')
            indiv_col = _find_net_col(target, '개인')

            # 숫자 변환 후 상위 5행 합산
            def sum_col(col):
                if col is None:
                    return 0
                vals = pd.to_numeric(target[col].head(5), errors='coerce').fillna(0)
                return int(vals.sum())

            investor_map[ticker] = {
                'frgn_net':       sum_col(frgn_col),
                'inst_net':       sum_col(inst_col),
                'pension_net':    0,
                'fin_invest_net': 0,
                'individual_net': sum_col(indiv_col),
            }
            success += 1

        except Exception as e:
            logger.warning('%s NAVER 수급 실패: %s', ticker, e)

    logger.info('NAVER 수급 완료: %d/%d개', success, len(tickers))
    return investor_map

# ─── 한국 스캔 ─────────────────────────────────────────────────────

def scan_kospi():
    logger.info('=== KOSPI 스캔 시작 ===')

    try:
        stocks_list = fdr.StockListing('KOSPI').head(50)
    except Exception as e:
        logger.error('KOSPI 종목 목록 로드 실패: %s', e)
        return

    tickers = stocks_list['Code'].tolist()
    investor_data = get_kr_investor_data(tickers)

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
