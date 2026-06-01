# stock-robot

KIS/HTS 스타일의 국내·해외 주식 조건검색 대시보드입니다.

## 구성

- `client`: Vite React UI
- `server`: NestJS + MongoDB API
- `scanner`: KOSPI/S&P500 후보 수집 스크립트

## 실행

```bash
cd client
npm install
npm run dev
```

기본 API 주소는 `http://localhost:3001`입니다. API가 아직 연결되지 않은 경우 UI는 샘플 데이터로 동작합니다.

서버 실행 시 MongoDB는 아래 환경변수를 사용합니다.

```bash
MONGODB_URI=mongodb+srv://...
MONGODB_DB=StockAnalysis
```

로컬에서 `mongodb+srv` DNS 조회가 실패하면 아래 값을 추가합니다.

```bash
MONGODB_DNS_SERVERS=8.8.8.8,1.1.1.1
```

`scanner`는 `MONGO_URI` 또는 `MONGODB_URI`를 읽습니다.
국내 수급은 KIS Open API 키가 있으면 공식 API를 우선 사용하고, 없거나 실패한 종목은 NAVER fallback을 시도합니다.

```bash
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_LOOKBACK_DAYS=5
```

## 현재 UI 기준

- 국내주식/KOSPI: KIS 수급 기반 후보 확인
- 해외주식/S&P500: 모멘텀 기반 후보 확인
- 필터: 전체, 매수 후보, 수급 동반, 리스크 낮음
- 상세 패널: 현재가, 목표/손절, 품질점수, 수급점수, 손익비, 수급 흐름

## 검증 원칙

화면의 신호는 매수 버튼이 아니라 후보 등급입니다. 실제 매수 신호로 쓰려면 1일, 3일, 7일 성과와 장중 목표/손절 터치율을 누적 검증해야 합니다.

