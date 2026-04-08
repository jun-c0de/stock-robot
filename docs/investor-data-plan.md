# 수급 데이터 개선 계획 — KIS Developers Open API 연동

## 배경

현재 수급 데이터(외국인/기관 순매수)가 모두 0으로 표시되는 문제가 있음.

**원인**: KRX(`www.krx.co.kr`)와 NAVER Finance 모두 GitHub Actions의 AWS 미국 IP 대역을 차단함.
- pykrx의 모든 수급 관련 함수 → `JSONDecodeError` (KRX 차단)
- NAVER Finance 스크래핑 → `No tables found` (NAVER 차단)
- OHLCV 가격 데이터(`marketdata.krx.co.kr`)는 정상 동작

---

## 해결 방안: KIS Developers Open API

한국투자증권 공식 REST API. IP 제한 없음. 무료.

### 준비 단계 (수동)

1. [https://apiportal.koreainvestment.com](https://apiportal.koreainvestment.com) 에서 회원가입
2. **앱 등록** → 모의투자 앱으로 등록 (무료, 심사 없음)
3. `APP_KEY`, `APP_SECRET` 발급
4. GitHub Repository → Settings → Secrets and variables → Actions에 추가:
   - `KIS_APP_KEY`
   - `KIS_APP_SECRET`

### 구현 내용

#### 1. 액세스 토큰 발급 (24시간마다 갱신 필요)

```python
def get_kis_token(app_key, app_secret):
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    resp = requests.post(url, json=body)
    return resp.json()["access_token"]
```

#### 2. 종목별 투자자별 순매수 조회

```
GET https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/investor
```

파라미터:
- `FID_COND_MRKT_DIV_CODE`: J (주식)
- `FID_INPUT_ISCD`: 종목코드 (예: 005930)

반환값: 외국인/기관/개인 순매수 포함

#### 3. scanner/main.py 변경 내용

- `get_kr_investor_data(tickers)` 함수를 KIS API 기반으로 교체
- `APP_KEY`, `APP_SECRET`은 환경변수(`KIS_APP_KEY`, `KIS_APP_SECRET`)로 관리
- 토큰 1회 발급 후 전체 종목 조회에 재사용

#### 4. scan.yml 변경 내용

```yaml
env:
  KIS_APP_KEY: ${{ secrets.KIS_APP_KEY }}
  KIS_APP_SECRET: ${{ secrets.KIS_APP_SECRET }}
```

---

## 기대 결과

- 외국인 순매수 (`frgn_net`) ✅
- 기관합계 순매수 (`inst_net`) ✅
- 연기금 순매수 (`pension_net`) ✅ (API에서 제공 시)
- 금융투자 순매수 (`fin_invest_net`) ✅ (API에서 제공 시)
- 개인 순매수 (`individual_net`) ✅

UI에서 외▲ 기▲ 연▲ 금▲ 개▲ 배지가 실제 데이터로 표시됨.
