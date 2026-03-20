import { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');

  // 1. 함수를 먼저 정의합니다.
  const fetchStocks = () => {
    axios.get('https://stock-robot.onrender.com/stocks')
      .then(res => {
        const scored = res.data.map(s => ({
          ...s,
          score: (s.position_pct * 0.4) + (s.rsi * 0.4) + (Math.abs(100 - s.disparity) * 0.2)
        })).sort((a, b) => a.score - b.score);
        setStocks(scored);
      })
      .catch(err => console.error(err));
  };

  // 2. 정의된 함수를 사용합니다.
  useEffect(() => { fetchStocks(); }, []);

  const filtered = filterMode === 'knee' ? stocks.filter(s => s.position_pct <= 40 && s.rsi <= 40) : stocks;

  return (
    <div className="container">
      <header className="header">
        <h1>💎 AI 저평가 탐지기</h1>
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
              <th>종목명 / 가이드</th>
              <th>현재가</th>
              <th className="desktop-only">무릎위치</th>
              <th className="desktop-only">RSI</th>
              <th>투자매력</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s._id}>
                <td className="stock-info">
                  <div className="stock-name">{s.name}</div>
                  <div className="stock-guide">
                    🎯 <span className="buy">{s.buy_target?.toLocaleString()}</span> |
                    🚀 <span className="sell">{s.sell_target?.toLocaleString()}</span> |
                    ⛔ <span className="stop">{s.stop_loss?.toLocaleString()}</span>
                  </div>
                </td>
                <td className="stock-price">
                  {s.price.toLocaleString()}원
                  <div className="mobile-only mobile-mini-stats">
                    {s.position_pct}% / RSI {s.rsi}
                  </div>
                </td>
                <td className="desktop-only">{s.position_pct}%</td>
                <td className="desktop-only">{s.rsi}</td>
                <td className="stock-score">
                  {s.score < 30 ? '⭐⭐⭐⭐⭐' : s.score < 50 ? '⭐⭐⭐' : '⭐'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default App;