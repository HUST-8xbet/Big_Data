import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Brush, ReferenceLine,
} from 'recharts';
import { Spin, Select, Tag, Typography } from 'antd';
import {
  ArrowLeftOutlined, SwapOutlined, ThunderboltOutlined,
  RiseOutlined, FallOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import '../styles/CoinDetail.css';

const { Title, Text } = Typography;
const { Option } = Select;

// ── API base ──────────────────────────────────────────────────────────────────
// ✅ Dynamic API URL - support cả localhost (dev) và Kubernetes
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_API = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

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
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

function fmtTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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
  const [loading,   setLoading]   = useState(true);
  const [timeRange, setTimeRange] = useState(60);    // phút

  // History mode: user đã kéo Brush ra khỏi live
  const [isHistoryMode, setIsHistoryMode] = useState(false);

  // WebSocket
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef        = useRef(null);
  const reconnectTmr = useRef(null);
  const isMounted    = useRef(true);

  // ── 1. Lấy danh sách coin từ market-summary ──────────────────────────────
  useEffect(() => {
    fetch(`${API}/api/market-summary`)
      .then(r => r.json())
      .then(data => setAvailableCoins(data.map(d => d.id)))
      .catch(() => {});
  }, []);

  // ── 2. Fetch lịch sử ──────────────────────────────────────────────────────
  const fetchHistory = useCallback((sym, minutes) => {
    setLoading(true);
    setRawData([]);
    setChartData([]);
    setIsHistoryMode(false);

    fetch(`${API}/api/historical-price/${sym}?minutes=${minutes}`)
      .then(r => r.json())
      .then(data => {
        if (!data.length) { setLoading(false); return; }
        const enriched = data.map((d, i) => ({
          ...d,
          _index: i,
          displayTime: d.time,
        }));
        setRawData(enriched);
        setLoading(false);
      })
      .catch(err => {
        console.error('Lỗi fetch lịch sử:', err);
        setLoading(false);
      });
  }, []);

  useEffect(() => { fetchHistory(coin, timeRange); }, [coin, timeRange, fetchHistory]);

  // ── 3. WebSocket ──────────────────────────────────────────────────────────
  const connectWs = useCallback((sym) => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }

    const ws = new WebSocket(`${WS_API}/ws/live-price/${sym}`);
    wsRef.current = ws;

    ws.onopen = () => { if (isMounted.current) setWsConnected(true); };

    ws.onmessage = (evt) => {
      if (!isMounted.current) return;
      const pt = JSON.parse(evt.data);
      setRawData(prev => {
        if (!prev.length) return prev;
        const last = prev[prev.length - 1];
        const newPt = {
          ...pt,
          _index: last._index + 1,
          displayTime: pt.time,
        };
        const next = [...prev, newPt];
        // Giới hạn raw data ≤ 2000 điểm
        return next.length > 2000 ? next.slice(next.length - 2000) : next;
      });
    };

    ws.onerror = () => {};
    ws.onclose = () => {
      if (!isMounted.current) return;
      setWsConnected(false);
      // Tự reconnect sau 3s
      reconnectTmr.current = setTimeout(() => connectWs(sym), 3000);
    };
  }, []);

  useEffect(() => {
    isMounted.current = true;
    connectWs(coin);
    return () => {
      isMounted.current = false;
      clearTimeout(reconnectTmr.current);
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, [coin, connectWs]);

  // ── 4. rawData → chartData (API đã trả đúng range, không cần slice) ──────
  useEffect(() => {
    setChartData(rawData);
  }, [rawData]);

  // ── 5. Stats cards ───────────────────────────────────────────────────────
  const stats = calcChange(chartData);
  const prices = chartData.map(d => d.real_price).filter(Boolean);
  const high = prices.length ? Math.max(...prices) : null;
  const low  = prices.length ? Math.min(...prices) : null;

  // ── 6. Display data — Brush tự xử lý zoom, không cần slice thủ công ───────
  const isLive = !isHistoryMode;
  const displayData = chartData;
  const currentPrice = chartData.length ? chartData[chartData.length - 1].real_price : null;

  // Brush window: mặc định hiện 120 điểm cuối, follow live khi không ở history mode
  const brushStartIndex = Math.max(0, displayData.length - 120);
  const brushEndIndex   = displayData.length > 0 ? displayData.length - 1 : 0;

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
          <Tag color={wsConnected ? 'green' : 'red'} icon={<ThunderboltOutlined />}>
            {wsConnected ? 'WS: Online' : 'WS: Offline'}
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
                onClick={() => { setTimeRange(tr.value); setScrubIndex(null); }}
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
                  domain={['auto', 'auto']}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => formatPrice(v)}
                  width={90}
                />
                <Tooltip content={<CustomTooltip />} />

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
                    startIndex={isHistoryMode ? undefined : brushStartIndex}
                    endIndex={isHistoryMode ? undefined : brushEndIndex}
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
