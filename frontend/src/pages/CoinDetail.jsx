import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Brush, ReferenceLine,
} from 'recharts';
import { Spin, Select, Tag, Typography } from 'antd';
// import ArrowLeftOutlined from '@ant-design/icons/ArrowLeftOutlined';
// import SwapOutlined from '@ant-design/icons/SwapOutlined';
// import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
// import RiseOutlined from '@ant-design/icons/RiseOutlined';
// import FallOutlined from '@ant-design/icons/FallOutlined';
// import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';
import {
  ArrowLeftOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  RiseOutlined,
  FallOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import '../styles/CoinDetail.css';

const { Title, Text } = Typography;
const { Option } = Select;

// ── API base ──────────────────────────────────────────────────────────────────
// ✅ Dynamic API URL - support cả localhost (dev) và Kubernetes
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── TIME RANGE options (minutes) ─────────────────────────────────────────────
const TIME_RANGES = [
  { label: '15 phút', value: 15 },
  { label: '30 phút', value: 30 },
  { label: '1 giờ',   value: 60  },
  { label: '2 giờ',   value: 120 },
  { label: '4 giờ',   value: 240 },
];

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatPrice(v) {
  if (v == null) return '–';
  const value = Number(v);
  const abs = Math.abs(value);
  const fractionDigits =
    abs >= 100 ? 2 :
    abs >= 1 ? 4 :
    abs >= 0.01 ? 6 :
    8;
  return '$' + value.toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function calcChange(p) {
  if (!p || p.length < 2) return { pct: 0, icon: null, color: '#9ca3af' };
  const first = p[0].real_price;
  const last  = p[p.length - 1].real_price;
  const pct   = ((last - first) / first) * 100;
  const icon  = pct >= 0 ? <RiseOutlined /> : <FallOutlined />;
  const color = pct > 0 ? '#52c41a' : pct < 0 ? '#ff4d4f' : '#9ca3af';
  return { pct, icon, color };
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="tooltip-time">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="tooltip-row">
          <span className="tooltip-dot" style={{ background: p.color }} />
          <span className="tooltip-label">{p.name}</span>
          <span className="tooltip-value" style={{ color: p.color }}>
            {formatPrice(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── CoinDetail Component ──────────────────────────────────────────────────────
export default function CoinDetail() {
  const { symbol: urlSymbol } = useParams();
  const navigate = useNavigate();

  // Đảm bảo symbol luôn viết hoa (VD: "btc" → "BTC")
  const [coin, setCoin]           = useState(urlSymbol ? urlSymbol.toUpperCase() : 'BTCUSDT');
  const [availableCoins, setAvailableCoins] = useState([]);

  // Dữ liệu
  const [rawData,   setRawData]   = useState([]);   // toàn bộ dữ liệu gốc
  const [chartData, setChartData] = useState([]);   // dữ liệu hiển thị (theo time range)
  const [forecast,  setForecast]  = useState([]);   // dự đoán tương lai (sau đường "Bây giờ")
  const [loading,   setLoading]   = useState(true);
  const [timeRange, setTimeRange] = useState(60);    // phút

  // History mode: user đã kéo Brush ra khỏi live
  const [isHistoryMode, setIsHistoryMode] = useState(false);

  const [liveConnected, setLiveConnected] = useState(false);

  // ── 1. Lấy danh sách coin từ market-summary ──────────────────────────────
  useEffect(() => {
    fetch(`${API}/api/market-summary`)
      .then(r => r.json())
      .then(data => setAvailableCoins(data.map(d => d.id)))
      .catch(() => {});
  }, []);

  // ── 2. Fetch lịch sử ──────────────────────────────────────────────────────
  // const fetchHistory = useCallback((sym, minutes, { silent = false } = {}) => {
  //   if (!silent) {
  //     setLoading(true);
  //     setRawData([]);
  //     setChartData([]);
  //     setIsHistoryMode(false);
  //   }

  //   fetch(`${API}/api/historical-price/${sym}?minutes=${minutes}`)
  //     .then(r => r.json())
  //     .then(data => {
  //       if (!data.length) {
  //         setLoading(false);
  //         setLiveConnected(false);
  //         return;
  //       }
  //       const enriched = data.map((d, i) => ({
  //         ...d,
  //         _index: i,
  //         displayTime: d.time,
  //       }));
  //       setRawData(enriched);
  //       setLiveConnected(true);
  //       setLoading(false);
  //     })
  //     .catch(err => {
  //       console.error('Lỗi fetch lịch sử:', err);
  //       setLiveConnected(false);
  //       setLoading(false);
  //     });
  // }, []);
  const fetchHistory = useCallback((sym, minutes, { silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
      setRawData([]);
      setChartData([]);
      setIsHistoryMode(false);
    }

    // ✅ Thêm logic: Tự động tính toán độ nén (interval) dựa vào số phút muốn xem
    let interval = '1m'; // Mặc định xem 15p, 30p thì lấy nến 1 phút
    if (minutes >= 240) interval = '5m';      // Nếu xem 4 giờ -> gộp thành nến 5 phút
    else if (minutes >= 120) interval = '3m'; // Nếu xem 2 giờ -> gộp thành nến 3 phút
    else if (minutes >= 60) interval = '2m';  // Nếu xem 1 giờ -> gộp thành nến 2 phút

    // ✅ Bổ sung tham số &interval=... vào URL API
    fetch(`${API}/api/historical-price/${sym}?minutes=${minutes}&interval=${interval}`)
      .then(r => r.json())
      .then(data => {
        if (!data.length) {
          setLoading(false);
          setLiveConnected(false);
          return;
        }
        const enriched = data.map((d, i) => ({
          ...d,
          _index: i,
          displayTime: d.time,
        }));
        setRawData(enriched);
        setLiveConnected(true);
        setLoading(false);
      })
      .catch(err => {
        console.error('Lỗi fetch lịch sử:', err);
        setLiveConnected(false);
        setLoading(false);
      });
  }, []);

  useEffect(() => { fetchHistory(coin, timeRange); }, [coin, timeRange, fetchHistory]);

  // Poll nến 1 phút. Không clear chart để tránh nhấp nháy/giật viewport.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!isHistoryMode) {
        fetchHistory(coin, timeRange, { silent: true });
      }
    }, 60000);
    return () => clearInterval(timer);
  }, [coin, timeRange, isHistoryMode, fetchHistory]);

  // ── 2b. Fetch dự đoán tương lai (sau đường "Bây giờ"), refresh mỗi 30s ────
  const fetchForecast = useCallback((sym) => {
    fetch(`${API}/api/forecast/${sym}?steps=15`)
      .then(r => r.json())
      .then(data => {
        setForecast(data.map(d => ({
          displayTime: d.time,
          predicted_price: d.predicted_price,
          isAnchor: Boolean(d.anchor),
          isForecast: true,
        })));
      })
      .catch(() => setForecast([]));
  }, []);

  useEffect(() => {
    setForecast([]);
    fetchForecast(coin);
    const timer = setInterval(() => fetchForecast(coin), 60000);
    return () => clearInterval(timer);
  }, [coin, fetchForecast]);

  // ── 4. rawData → chartData (API đã trả đúng range, không cần slice) ──────
  useEffect(() => {
    setChartData(rawData);
  }, [rawData]);

  // ── 5. Stats cards ───────────────────────────────────────────────────────
  const stats = calcChange(chartData);
  const prices = chartData.map(d => d.real_price).filter(Boolean);
  const high = prices.length ? Math.max(...prices) : null;
  const low  = prices.length ? Math.min(...prices) : null;

  // ── 6. Display data — lịch sử + dự đoán tương lai sau đường "Bây giờ" ─────
  const isLive = !isHistoryMode;
  const currentPrice = chartData.length ? chartData[chartData.length - 1].real_price : null;
  const nowTime = chartData.length ? chartData[chartData.length - 1].displayTime : null;
  const futureForecast = useMemo(
    () => (forecast[0]?.isAnchor ? forecast.slice(1) : forecast),
    [forecast]
  );
  const historicalDisplayData = useMemo(() => chartData.map((point, index) => ({
    ...point,
    // Historical one-step predictions are useful for debugging, but visually
    // they make the forecast line look like it has already predicted the past.
    predicted_price: index === chartData.length - 1 && forecast.length > 0
      ? point.real_price
      : null,
  })), [chartData, forecast.length]);
  const displayData = useMemo(
    () => (chartData.length ? [...historicalDisplayData, ...futureForecast] : chartData),
    [chartData, historicalDisplayData, futureForecast]
  );

  const yDomain = useMemo(() => {
    const values = displayData.flatMap(d => [d.real_price, d.predicted_price]).filter(v => v != null);
    if (!values.length) return ['auto', 'auto'];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max((max - min) * 0.08, Math.abs(max || 1) * 0.0005);
    return [min - pad, max + pad];
  }, [displayData]);

  return (
    <div className="detail-page">

      {/* ── Header ── */}
      <header className="detail-header">
        <button className="btn-back" onClick={() => navigate('/')}>
          <ArrowLeftOutlined /> Bảng giá
        </button>

        <div className="header-center">
          <Select
            value={coin}
            onChange={(v) => setCoin(v)}
            className="coin-selector"
            popupClassName="coin-selector-dropdown"
            suffixIcon={<SwapOutlined />}
          >
            {availableCoins.map(s => (
              <Option key={s} value={s}>{s}</Option>
            ))}
          </Select>

          <div className="live-badge" data-live={isLive}>
            <span className="live-dot" />
            {isLive ? 'Trực tiếp' : 'Lịch sử'}
          </div>
        </div>

        <div className="header-status">
          <Tag color={liveConnected ? 'green' : 'red'} icon={<ThunderboltOutlined />}>
            {liveConnected ? 'Live: On' : 'Live: Syncing'}
          </Tag>
        </div>
      </header>

      {/* ── Stats Row ── */}
      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">Giá hiện tại</span>
          <span className="stat-value primary">{formatPrice(currentPrice)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Cao nhất ({TIME_RANGES.find(t => t.value === timeRange)?.label})</span>
          <span className="stat-value up">{formatPrice(high)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Thấp nhất ({TIME_RANGES.find(t => t.value === timeRange)?.label})</span>
          <span className="stat-value down">{formatPrice(low)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Biến động</span>
          <span className="stat-value" style={{ color: stats.color }}>
            {stats.icon} {stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Điểm dữ liệu</span>
          <span className="stat-value neutral">{displayData.length}</span>
        </div>
      </div>

      {/* ── Chart Area ── */}
      <div className="chart-area">
        {/* Toolbar */}
        <div className="chart-toolbar">
          <div className="time-range-group">
            {TIME_RANGES.map(tr => (
              <button
                key={tr.value}
                className={`range-btn ${timeRange === tr.value && isLive ? 'active' : ''}`}
                onClick={() => setTimeRange(tr.value)}
              >
                {tr.label}
              </button>
            ))}
          </div>

          {!isLive && (
            <button className="btn-live-hint" onClick={() => setIsHistoryMode(false)}>
              ← Quay về Live
            </button>
          )}
        </div>

        {/* Recharts */}
        <div className="chart-wrapper">
          {loading ? (
            <div className="chart-loading">
              <Spin size="large" />
              <Text type="secondary">Đang tải dữ liệu...</Text>
            </div>
          ) : displayData.length === 0 ? (
            <div className="chart-loading">
              <InfoCircleOutlined style={{ fontSize: 32, color: '#9ca3af' }} />
              <Text type="secondary">Không có dữ liệu cho {coin}</Text>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={displayData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="displayTime"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={yDomain}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => formatPrice(v)}
                  width={90}
                />
                <Tooltip content={<CustomTooltip />} />

                {/* Đường kẻ dọc "Bây giờ" — bên phải là dự đoán tương lai */}
                {nowTime && forecast.length > 0 && (
                  <ReferenceLine
                    x={nowTime}
                    stroke="#ffd700"
                    strokeDasharray="4 4"
                    strokeWidth={1.5}
                    label={{
                      value: '◀ Bây giờ | Dự đoán ▶',
                      position: 'insideTopRight',
                      fill: '#ffd700',
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  />
                )}

                {/* Đường giá thực tế */}
                <Line
                  type="monotone"
                  dataKey="real_price"
                  name="Giá Thực Tế"
                  stroke="#00e396"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                  activeDot={{ r: 5, fill: '#00e396', strokeWidth: 0 }}
                />

                {/* Đường AI dự đoán */}
                <Line
                  type="monotone"
                  dataKey="predicted_price"
                  name="AI Dự Đoán"
                  stroke="#ff6b6b"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  dot={false}
                  isAnimationActive={false}
                  activeDot={{ r: 4, fill: '#ff6b6b', strokeWidth: 0 }}
                />

                {/* Brush — kéo thả để xem quá khứ, Recharts tự xử lý zoom */}
                {displayData.length > 10 && (
                  <Brush
                    dataKey="displayTime"
                    height={28}
                    stroke="rgba(255,255,255,0.15)"
                    fill="#1e2230"
                    travellerWidth={8}
                    onChange={(state) => {
                      if (!state) return;
                      // Nếu end chưa đến cuối → history mode
                      const atEnd = state.endIndex >= displayData.length - 1;
                      setIsHistoryMode(!atEnd);
                    }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Scrub hint */}
        <div className="chart-hint">
          <InfoCircleOutlined /> Di chuyển chuột trên biểu đồ hoặc dùng thanh Brush bên dưới để xem lịch sử
        </div>
      </div>

      {/* ── Footer ── */}
      <footer className="detail-footer">
        <Text type="secondary">
          {coin} · Dữ liệu từ InfluxDB · Batch Layer cập nhật mỗi 10 phút
        </Text>
      </footer>
    </div>
  );
}
