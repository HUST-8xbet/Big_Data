import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import CoinDetail from './pages/CoinDetail';
import './App.css'; // Giữ lại CSS tổng nếu có

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Trang chủ: localhost:5173/ */}
        <Route path="/" element={<Home />} />
        
        {/* Trang chi tiết: localhost:5173/coin/btc */}
        <Route path="/coin/:symbol" element={<CoinDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;