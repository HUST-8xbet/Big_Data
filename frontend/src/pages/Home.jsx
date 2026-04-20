import { useState, useEffect, useMemo } from 'react';
import { Table, Input, Typography, Tag } from 'antd';
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
const API = process.env.VITE_API_URL || 'http://localhost:8000';

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
        <BarChartOutlined className="mstat-icon" />
        <div>
          <span className="mstat-value">{total}</span>
          <span className="mstat-label">Coin theo dõi</span>
        </div>
      </div>
      <div className="mstat-card up">
        <RiseOutlined className="mstat-icon" />
        <div>
          <span className="mstat-value">{gainers}</span>
          <span className="mstat-label">Tăng giá</span>
        </div>
      </div>
      <div className="mstat-card down">
        <FallOutlined className="mstat-icon" />
        <div>
          <span className="mstat-value">{losers}</span>
          <span className="mstat-label">Giảm giá</span>
        </div>
      </div>
      <div className="mstat-card">
        <DollarOutlined className="mstat-icon" />
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
  const [loading,    setLoading]    = useState(true);
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${API}/api/market-summary`)
      .then(r => r.json())
      .then(json => { setData(json); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = useMemo(() =>
    data.filter(coin =>
      coin.name.toLowerCase().includes(searchText.toLowerCase()) ||
      coin.symbol.toLowerCase().includes(searchText.toLowerCase())
    ),
    [data, searchText]
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
          <ThunderboltOutlined className="brand-icon" />
          <Title level={2} style={{ margin: 0, color: 'var(--text-h)' }}>
            CryptoWatch
          </Title>
        </div>
        <Tag icon={<ThunderboltOutlined />} style={{ borderRadius: 20 }}>
          Live Data
        </Tag>
      </header>

      {/* ── Market Stats ── */}
      <MarketStats data={data} />

      {/* ── Search + Table ── */}
      <div className="table-section">
        <div className="table-header">
          <Text strong style={{ color: 'var(--text-h)', fontSize: 16 }}>
            Bảng giá thị trường
          </Text>
          <Search
            placeholder="Tìm coin (BTC, ETH, SOL...)"
            allowClear
            prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
            onChange={e => setSearchText(e.target.value)}
            className="search-input"
          />
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
