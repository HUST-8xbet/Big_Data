import { useState, useEffect, useMemo, useRef } from 'react';
import { Table, Input, InputNumber, Typography, Tag, notification } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, ResponsiveContainer, YAxis, ReferenceLine,
} from 'recharts';
import {
  RiseOutlined, FallOutlined, ThunderboltOutlined,
  SearchOutlined, BarChartOutlined, DollarOutlined,
} from '@ant-design/icons';
import '../styles/Home.css';

const { Title, Text } = Typography;
const { Search } = Input;

// ── API ──────────────────────────────────────────────────────────────────────
// ✅ Dynamic API URL - support cả localhost (dev) và Kubernetes
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatPrice(v) {
  if (v == null) return '–';
  return '$' + Number(v).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtPct(v) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${Number(v).toFixed(2)}%`;
}

// ── Mini Sparkline ───────────────────────────────────────────────────────────
function Sparkline({ data, positive }) {
  const chartData = data.map((v, i) => ({ v, i }));
  const color = positive ? '#00e396' : '#ff4d4f';
  const refVal = data[0] ?? 0;

  return (
    <div className="sparkline-wrap">
      <ResponsiveContainer width="100%" height={40}>
        <LineChart data={chartData}>
          <YAxis domain={['dataMin', 'dataMax']} hide />
          <ReferenceLine
            y={refVal}
            stroke="rgba(255,255,255,0.1)"
            strokeDasharray="3 3"
          />
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Header Clock ─────────────────────────────────────────────────────────────
function HeaderClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fmt = (tz) => now.toLocaleTimeString('vi-VN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false, timeZone: tz,
  });

  return (
    <div className="header-clock">
      <div className="clock-item">
        <span className="clock-label">Việt Nam</span>
        <span className="clock-value">{fmt('Asia/Ho_Chi_Minh')}</span>
      </div>
      <div className="clock-divider" />
      <div className="clock-item">
        <span className="clock-label">UTC</span>
        <span className="clock-value">{fmt('UTC')}</span>
      </div>
    </div>
  );
}

// ── Market Summary Stats ─────────────────────────────────────────────────────
function MarketStats({ data }) {
  const total  = data.length;
  const gainers = data.filter(d => d.price_change_percentage_24h > 0).length;
  const losers  = data.filter(d => d.price_change_percentage_24h < 0).length;
  const avgChg  = data.length
    ? data.reduce((s, d) => s + d.price_change_percentage_24h, 0) / total
    : 0;

  return (
    <div className="market-stats">
      <div className="mstat-card">
        <div className="mstat-icon-wrap">
          <BarChartOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{total}</span>
          <span className="mstat-label">Coin theo dõi</span>
        </div>
      </div>
      <div className="mstat-card up">
        <div className="mstat-icon-wrap">
          <RiseOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{gainers}</span>
          <span className="mstat-label">Tăng giá</span>
        </div>
      </div>
      <div className="mstat-card down">
        <div className="mstat-icon-wrap">
          <FallOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{losers}</span>
          <span className="mstat-label">Giảm giá</span>
        </div>
      </div>
      <div className="mstat-card">
        <div className="mstat-icon-wrap">
          <DollarOutlined className="mstat-icon" />
        </div>
        <div>
          <span
            className="mstat-value"
            style={{ color: avgChg >= 0 ? '#00e396' : '#ff4d4f' }}
          >
            {fmtPct(avgChg)}
          </span>
          <span className="mstat-label">Biến động TB</span>
        </div>
      </div>
    </div>
  );
}

// ── Home ──────────────────────────────────────────────────────────────────────
export default function Home() {
  const [data,       setData]       = useState([]);
  const prevDataRef  = useRef({});
  const [loading,    setLoading]    = useState(true);
  const [searchText, setSearchText] = useState('');
  const [minPrice,   setMinPrice]   = useState(null);
  const [maxPrice,   setMaxPrice]   = useState(null);
  const navigate = useNavigate();

  // ── Fetch initial data ──
  useEffect(() => {
    fetch(`${API}/api/market-summary`)
      .then(r => r.json())
      .then(json => { 
        setData(json); 
        setLoading(false);
        // Initialize prevData
        prevDataRef.current = {};
        json.forEach(coin => {
          prevDataRef.current[coin.id] = coin.price_change_percentage_24h;
        });
      })
      .catch(() => setLoading(false));
  }, []);

  // ── Fetch updated data every 10 seconds and check for drops ──
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API}/api/market-summary`)
        .then(r => r.json())
        .then(json => {
          json.forEach(coin => {
            const prevChange = prevDataRef.current[coin.id];
            const currentChange = coin.price_change_percentage_24h;
            
            // Check if change dropped (became more negative or increased less)
            if (prevChange !== undefined && currentChange < prevChange) {
              notification.warning({
                message: `${coin.symbol.toUpperCase()} - Giá đang giảm`,
                description: `Biến động: ${fmtPct(prevChange)} → ${fmtPct(currentChange)}`,
                placement: 'topRight',
                duration: 4,
              });
            }
          });
          
          // Update data and prevDataRef
          setData(json);
          prevDataRef.current = {};
          json.forEach(coin => {
            prevDataRef.current[coin.id] = coin.price_change_percentage_24h;
          });
        })
        .catch(() => {});
    }, 10000); // Update every 10 seconds
    
    return () => clearInterval(interval);
  }, []);

  const filtered = useMemo(() =>
    data.filter(coin => {
      // Filter by search text
      const matchesSearch = coin.name.toLowerCase().includes(searchText.toLowerCase()) ||
                            coin.symbol.toLowerCase().includes(searchText.toLowerCase());
      
      // Filter by price range
      const price = coin.current_price;
      const aboveMin = minPrice === null || price >= minPrice;
      const belowMax = maxPrice === null || price <= maxPrice;
      
      return matchesSearch && aboveMin && belowMax;
    }),
    [data, searchText, minPrice, maxPrice]
  );

  const columns = [
    {
      title: 'Tên',
      key: 'name',
      render: (_, record) => (
        <div className="coin-cell">
          <div className="coin-icon">
            {record.name?.charAt(0) ?? '?'}
          </div>
          <div>
            <Text strong style={{ color: 'var(--text-h)' }}>{record.name}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>{record.symbol.toUpperCase()}</Text>
          </div>
        </div>
      ),
    },
    {
      title: 'Giá (USD)',
      dataIndex: 'current_price',
      key: 'price',
      align: 'right',
      sorter: (a, b) => a.current_price - b.current_price,
      render: (v) => (
        <Text strong style={{ color: '#e8e8e8', fontFamily: 'var(--mono)' }}>
          {formatPrice(v)}
        </Text>
      ),
    },
    {
      title: 'Biến động',
      dataIndex: 'price_change_percentage_24h',
      key: 'change',
      align: 'right',
      sorter: (a, b) => a.price_change_percentage_24h - b.price_change_percentage_24h,
      width: 130,
      render: (v) => {
        const up = v >= 0;
        return (
          <Tag
            color={up ? 'green' : 'red'}
            style={{ borderRadius: 20, fontWeight: 600, minWidth: 72, textAlign: 'center', justifyContent: 'center' }}
          >
            {up ? <RiseOutlined /> : <FallOutlined />}
            {' '}{fmtPct(v)}
          </Tag>
        );
      },
    },
    {
      title: 'Xu hướng 2h',
      dataIndex: 'sparkline',
      key: 'sparkline',
      align: 'center',
      width: 140,
      render: (vals, record) => (
        <Sparkline data={vals} positive={record.price_change_percentage_24h >= 0} />
      ),
    },
  ];

  return (
    <div className="home-page">
      {/* ── Header ── */}
      <header className="home-header">
        <div className="header-brand">
          <div className="brand-icon-wrap">
            <ThunderboltOutlined className="brand-icon" />
          </div>
          <div>
            <Title level={2} className="brand-title">CryptoWatch</Title>
            <Text className="brand-subtitle">Theo dõi thị trường crypto theo thời gian thực</Text>
          </div>
        </div>
        <div className="header-right">
          <HeaderClock />
          <div className="home-live-badge">
            <span className="home-live-dot" />
            Live Data
          </div>
        </div>
      </header>

      {/* ── Market Stats ── */}
      <MarketStats data={data} />

      {/* ── Search + Table ── */}
      <div className="table-section">
        <div className="table-header">
          <Text strong style={{ color: 'var(--text-h)', fontSize: 16 }}>
            Bảng giá thị trường
          </Text>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <Search
              placeholder="Tìm coin (BTC, ETH, SOL...)"
              allowClear
              prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
              onChange={e => setSearchText(e.target.value)}
              className="search-input"
            />
            <InputNumber
              placeholder="Giá tối thiểu"
              min={0}
              value={minPrice}
              onChange={setMinPrice}
              style={{ width: 140 }}
            />
            <span style={{ color: '#6b7280' }}>—</span>
            <InputNumber
              placeholder="Giá tối đa"
              min={0}
              value={maxPrice}
              onChange={setMaxPrice}
              style={{ width: 140 }}
            />
          </div>
        </div>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            style: { color: '#9ca3af' },
          }}
          onRow={(record) => ({
            onClick: () => navigate(`/coin/${record.symbol}`),
            style: { cursor: 'pointer' },
          })}
          locale={{ emptyText: 'Không tìm thấy coin nào.' }}
        />
      </div>

      <footer className="home-footer">
        <Text type="secondary" style={{ fontSize: 12 }}>
          Dữ liệu giá từ Binance · Batch Layer cập nhật mỗi 10 phút · Speed Layer real-time
        </Text>
      </footer>
    </div>
  );
}
