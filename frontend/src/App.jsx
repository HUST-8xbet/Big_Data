import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';

const Home = lazy(() => import('./pages/Home'));
const CoinDetail = lazy(() => import('./pages/CoinDetail'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/coin/:symbol" element={<CoinDetail />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
