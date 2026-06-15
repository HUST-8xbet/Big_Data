import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css'; // Giữ lại CSS tổng nếu có

const Home = lazy(() => import('./pages/Home'));
const CoinDetail = lazy(() => import('./pages/CoinDetail'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          {/* Trang chủ: localhost:5173/ */}
          <Route path="/" element={<Home />} />
          
          {/* Trang chi tiết: localhost:5173/coin/btc */}
          <Route path="/coin/:symbol" element={<CoinDetail />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
