import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3001';

function App() {
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStocks = () => {
    setLoading(true);
    setError(null);
    axios.get(`${API_URL}/stocks?limit=200`)
      .then(res => {
        const scored = res.data.data.map(s => ({
          ...s,
          score: (s.position_pct * 0.4) + (s.rsi * 0.4) + (Math.abs(100 - s.disparity) * 0.2)
        })).sort((a, b) => a.score - b.score);
        setStocks(scored);
      })
      .catch(err => {
        console.error(err);
        setError('데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchStocks(); }, []);

  const filtered = useMemo(
    () => filterMode === 'knee' ? stocks.filter(s => s.position_pct <= 40 && s.rsi <= 40) : stocks,
    [stocks, filterMode]
  );

  return (
    <div className="container">
      <header className="header">
        <h1>💎 AI 저평가 탐지기</h1>
        <div className="filter-buttons">
          <button onClick={() => setFilterMode('all')} className={filterMode === 'all' ? 'active' : ''}>전체</button>
          <button onClick={() => setFilterMode('knee')} className={`knee-btn ${filterMode === 'knee' ? 'active' : ''}`}>🔥 강력 추천</button>
        </div>
      </header>

      {loading && <div className="status-message">데이터를 불러오는 중...</div>}
      {error && (
        <div className="error-message">
          {error}
          <button onClick={fetchStocks} className="retry-btn">다시 시도</button>
        </div>
      )}

      {!loading && !error && (
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
                    <div className="price-val">{s.price?.toLocaleString()}원</div>
                    <div className="mini-stats">무릎 {s.position_pct}% / RSI {s.rsi}</div>
                    <div className="price-guide">
                      <span className="buy-tag">🎯 {s.buy_target?.toLocaleString()}</span>
                      <span className="sell-tag">🚀 {s.sell_target?.toLocaleString()}</span>
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
      )}
    </div>
  );
}

export default App;
