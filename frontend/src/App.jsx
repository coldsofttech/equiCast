import { useState } from "react";

function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);

  const fetchHistory = async () => {
    setError(null);
    try {
      const response = await fetch(`/api/market-data/${ticker}/`);
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      const data = await response.json();
      setHistory(data.results);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <main>
      <h1>equiCast</h1>
      <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} />
      <button onClick={fetchHistory}>Fetch history</button>
      {error && <p role="alert">{error}</p>}
      <p>{history.length} rows loaded</p>
    </main>
  );
}

export default App;
