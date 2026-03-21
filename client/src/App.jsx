import { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');

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
              <th className="th-info">종목 / 수급</th>
              <th className="th-price">현재가 / 가이드</th>
              <th className="th-score">투자매력</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s._id}>
                <td className="stock-info">
                  <div className="name-box">
                    <span className="stock-name">{s.name}</span>
                    {s.is_double_buy && <span className="hot-badge">PUMPING 🔥</span>}
                  </div>
                  <div className="investor-row">
                    <span className={s.frgn_buy > 0 ? 'plus' : 'neutral'}>
                      외 {s.frgn_buy > 0 ? '▲' : '·'}
                    </span>
                    <span className={s.inst_buy > 0 ? 'plus' : 'neutral'}>
                      기 {s.inst_buy > 0 ? '▲' : '·'}
                    </span>
                  </div>
                </td>

                <td className="stock-price-cell">
                  <div className="price-val">{s.price.toLocaleString()}원</div>
                  <div className="mini-stats">
                    무릎 {s.position_pct}% / RSI {s.rsi}
                  </div>
                  <div className="price-guide">
                    <span className="buy-tag">🎯 {s.buy_target?.toLocaleString()}</span>
                    <span className="sell-target">🚀 {s.sell_target?.toLocaleString()}</span>
                    <span className="stop-tag">🛑 {s.stop_loss?.toLocaleString()}</span>
                  </div>
                </td>

                <td className="stock-score">
                  {s.score < 30 ? '⭐⭐⭐⭐⭐' : s.score < 45 ? '⭐⭐⭐' : '⭐'}
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