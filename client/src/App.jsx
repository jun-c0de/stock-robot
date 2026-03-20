import { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css'; // 별도 CSS 파일을 사용할 것입니다.

function App() {
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');

  useEffect(() => { fetchStocks(); }, []);

  const fetchStocks = () => {
    // 본인의 Render 주소로 변경하세요!
    axios.get('https://stock-robot.onrender.com/stocks')
      .then(res => {
        // 점수 계산 로직 (낮을수록 저평가)
        const scored = res.data.map(s => ({
          ...s,
          score: (s.position_pct * 0.4) + (s.rsi * 0.4) + (Math.abs(100 - s.disparity) * 0.2)
        })).sort((a, b) => a.score - b.score);
        setStocks(scored);
      })
      .catch(err => console.error("데이터 로드 실패:", err));
  };

  const filtered = filterMode === 'knee' ? stocks.filter(s => s.position_pct <= 40 && s.rsi <= 40) : stocks;

  return (
    <div className="container">
      <header className="header">
        <h1>💎 AI 주식 저평가 탐지기</h1>
        <div className="filter-buttons">
          <button onClick={() => setFilterMode('all')} className={filterMode === 'all' ? 'active' : ''}>전체</button>
          <button onClick={() => setFilterMode('knee')} className={`knee-btn ${filterMode === 'knee' ? 'active' : ''}`}>
            🔥 강력 추천
          </button>
        </div>
      </header>

      <div className="table-wrapper">
        <table className="stock-table">
          <thead>
            <tr>
              <th>종목명</th>
              <th>현재가</th>
              <th className="desktop-only">무릎위치</th>
              <th className="desktop-only">RSI</th>
              <th className="desktop-only">이격도</th>
              <th>투자매력</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => {
              const isKnee = s.position_pct < 30;
              const isRsiLow = s.rsi < 30;
              return (
                <tr key={s._id}>
                  <td className="stock-name">
                    {s.name}
                    {/* 모바일에서만 보이는 상세 정보 한 줄 */}
                    <div className="mobile-only mobile-details">
                      위치: <span className={isKnee ? 'highlight' : ''}>{s.position_pct}%</span> |
                      RSI: <span className={isRsiLow ? 'highlight' : ''}>{s.rsi}</span>
                    </div>
                  </td>
                  <td className="stock-price">{s.price.toLocaleString()}원</td>
                  <td className="desktop-only">{s.position_pct}%</td>
                  <td className="desktop-only">{s.rsi}</td>
                  <td className="desktop-only">{s.disparity}%</td>
                  <td className="stock-score">
                    {s.score < 30 ? '⭐⭐⭐⭐⭐' : s.score < 50 ? '⭐⭐⭐' : '⭐'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default App;