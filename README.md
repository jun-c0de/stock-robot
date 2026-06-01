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

## 현재 UI 기준

- 국내주식/KOSPI: KIS 수급 기반 후보 확인
- 해외주식/S&P500: 모멘텀 기반 후보 확인
- 필터: 전체, 매수 후보, 수급 동반, 리스크 낮음
- 상세 패널: 현재가, 목표/손절, 품질점수, 수급점수, 손익비, 수급 흐름

## 검증 원칙

화면의 신호는 매수 버튼이 아니라 후보 등급입니다. 실제 매수 신호로 쓰려면 1일, 3일, 7일 성과와 장중 목표/손절 터치율을 누적 검증해야 합니다.

