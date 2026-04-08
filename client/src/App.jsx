import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3001';

const MARKETS = [
  { key: 'KOSPI', label: '🇰🇷 KOSPI' },
  { key: 'SP500', label: '🇺🇸 S&P500' },
];

function InvestorBadge({ value, label }) {
  const active = value > 0;
  return (
    <span className={active ? 'inv-badge plus' : 'inv-badge neutral'}>
      {label} {active ? '▲' : '·'}
    </span>
  );
}

function App() {
  const [market, setMarket] = useState('KOSPI');
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStocks = (selectedMarket) => {
    setLoading(true);
    setError(null);
    axios.get(`${API_URL}/stocks?market=${selectedMarket}&limit=200`)
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

  useEffect(() => {
    setFilterMode('all');
    fetchStocks(market);
  }, [market]);

  const filtered = useMemo(
    () => filterMode === 'knee' ? stocks.filter(s => s.position_pct <= 40 && s.rsi <= 40) : stocks,
    [stocks, filterMode]
  );

  const isKospi = market === 'KOSPI';

  const formatPrice = (price, currency) => {
    if (currency === 'USD') return `$${Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return `${Number(price).toLocaleString()}원`;
  };

  return (
    <div className="container">
      <header className="header">
        <h1>💎 AI 저평가 탐지기</h1>
        <div className="market-tabs">
          {MARKETS.map(m => (
            <button
              key={m.key}
              onClick={() => setMarket(m.key)}
              className={`market-tab ${market === m.key ? 'active' : ''}`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="filter-buttons">
          <button onClick={() => setFilterMode('all')} className={filterMode === 'all' ? 'active' : ''}>전체</button>
          <button onClick={() => setFilterMode('knee')} className={`knee-btn ${filterMode === 'knee' ? 'active' : ''}`}>🔥 강력 추천</button>
        </div>
      </header>

      {loading && <div className="status-message">데이터를 불러오는 중...</div>}
      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => fetchStocks(market)} className="retry-btn">다시 시도</button>
        </div>
      )}

      {!loading && !error && (
        <div className="table-wrapper">
          <table className="stock-table">
            <thead>
              <tr>
                <th className="th-info">종목{isKospi ? ' / 수급' : ''}</th>
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
                    {isKospi && (
                      <div className="investor-row">
                        <InvestorBadge value={s.frgn_net} label="외" />
                        <InvestorBadge value={s.inst_net} label="기" />
                        <InvestorBadge value={s.pension_net} label="연" />
                        <InvestorBadge value={s.fin_invest_net} label="금" />
                        <InvestorBadge value={s.individual_net} label="개" />
                      </div>
                    )}
                  </td>
                  <td className="stock-price-cell">
                    <div className="price-val">{formatPrice(s.price, s.currency)}</div>
                    <div className="mini-stats">무릎 {s.position_pct}% / RSI {s.rsi}</div>
                    <div className="price-guide">
                      <span className="buy-tag">🎯 {formatPrice(s.buy_target, s.currency)}</span>
                      <span className="sell-tag">🚀 {formatPrice(s.sell_target, s.currency)}</span>
                      <span className="stop-tag">🛑 {formatPrice(s.stop_loss, s.currency)}</span>
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
