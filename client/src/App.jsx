import { useEffect, useState } from 'react';
import axios from 'axios';

function App() {
  const [stocks, setStocks] = useState([]);
  const [filterMode, setFilterMode] = useState('all');

  useEffect(() => { fetchStocks(); }, []);

  const fetchStocks = () => {
    axios.get('http://localhost:3001/stocks')
      .then(res => {
        // 점수 계산 로직 추가 (낮을수록 좋음: 저평가)
        const scored = res.data.map(s => ({
          ...s,
          score: (s.position_pct * 0.4) + (s.rsi * 0.4) + (Math.abs(100 - s.disparity) * 0.2)
        })).sort((a, b) => a.score - b.score);
        setStocks(scored);
      });
  };

  const filtered = filterMode === 'knee' ? stocks.filter(s => s.position_pct <= 40 && s.rsi <= 40) : stocks;

  return (
    <div style={{ padding: '20px', backgroundColor: '#f4f7f6', minHeight: '100vh' }}>
      <h1>💎 AI 주식 저평가 탐지기</h1>
      <div style={{ marginBottom: '20px' }}>
        <button onClick={() => setFilterMode('all')}>전체</button>
        <button onClick={() => setFilterMode('knee')} style={{ marginLeft: '10px', backgroundColor: '#e67e22', color: 'white' }}>
          🔥 강력 추천 (무릎 + 과매도)
        </button>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
        <thead>
          <tr style={{ backgroundColor: '#2c3e50', color: 'white' }}>
            <th>종목명</th>
            <th>현재가</th>
            <th>무릎위치</th>
            <th>RSI</th>
            <th>이격도</th>
            <th>투자매력</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(s => (
            <tr key={s._id} style={{ borderBottom: '1px solid #eee', textAlign: 'center' }}>
              <td style={{ padding: '15px', fontWeight: 'bold' }}>{s.name}</td>
              <td>{s.price.toLocaleString()}원</td>
              <td style={{ color: s.position_pct < 30 ? '#e74c3c' : 'black' }}>{s.position_pct}%</td>
              <td style={{ color: s.rsi < 30 ? '#e74c3c' : 'black' }}>{s.rsi}</td>
              <td>{s.disparity}%</td>
              <td>
                {s.score < 30 ? '⭐⭐⭐⭐⭐' : s.score < 50 ? '⭐⭐⭐' : '⭐'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export default App;