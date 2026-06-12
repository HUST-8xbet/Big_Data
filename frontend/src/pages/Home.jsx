import { useState, useEffect, useMemo, useCallback } from 'react';
import { Table, Input, InputNumber, Typography, Tag, notification, Button, Modal, Select } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, ResponsiveContainer, YAxis, ReferenceLine,
} from 'recharts';
import {
  RiseOutlined, FallOutlined, ThunderboltOutlined,
  SearchOutlined, BarChartOutlined, DollarOutlined,
  BellOutlined, DeleteOutlined, PlusOutlined,
} from '@ant-design/icons';
import '../styles/Home.css';

const { Title, Text } = Typography;
const { Search } = Input;

// ── API ──────────────────────────────────────────────────────────────────────
// ✅ Dynamic API URL - support cả localhost (dev) và Kubernetes
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ALERTS_STORAGE_KEY = 'cryptowatch_price_alerts';

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
  return '$' + Number(v).toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function fmtPct(v) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${Number(v).toFixed(2)}%`;
}

function makeAlertId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isAlertTriggered(alert, price) {
  return alert.direction === 'below'
    ? price <= alert.targetPrice
    : price >= alert.targetPrice;
}

function alertDescription(alert, currentPrice) {
  const directionText = alert.direction === 'below' ? 'dưới hoặc bằng' : 'trên hoặc bằng';
  return `Giá hiện tại ${formatPrice(currentPrice)} đã ${directionText} ${formatPrice(alert.targetPrice)}`;
}

function alertNotificationKey(alert) {
  return `price-alert-${alert.id}`;
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
  const [loading,    setLoading]    = useState(true);
  const [searchText, setSearchText] = useState('');
  const [minPrice,   setMinPrice]   = useState(null);
  const [maxPrice,   setMaxPrice]   = useState(null);
  const [alertOpen,  setAlertOpen]  = useState(false);
  const [alertSymbol, setAlertSymbol] = useState(null);
  const [alertDirection, setAlertDirection] = useState('below');
  const [alertPrice, setAlertPrice] = useState(null);
  const [alerts, setAlerts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(ALERTS_STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  });
  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts));
  }, [alerts]);

  const evaluateAlerts = useCallback((marketData) => {
    const coinBySymbol = new Map(marketData.map(coin => [coin.id, coin]));

    setAlerts(currentAlerts => {
      let changed = false;

      const nextAlerts = currentAlerts.map(alert => {
        const coin = coinBySymbol.get(alert.symbol);
        if (!coin || coin.current_price == null) return alert;

        const currentPrice = Number(coin.current_price);
        const triggered = isAlertTriggered(alert, currentPrice);
        const wasTriggered = Boolean(alert.triggered);

        if (triggered && !wasTriggered) {
          notification.warning({
            key: alertNotificationKey(alert),
            message: `${alert.symbol} chạm ngưỡng giá`,
            description: alertDescription(alert, currentPrice),
            placement: 'topRight',
            duration: 6,
          });
        }

        if (triggered !== wasTriggered) {
          changed = true;
          return {
            ...alert,
            triggered,
            lastTriggeredAt: triggered ? Date.now() : alert.lastTriggeredAt,
          };
        }

        return alert;
      });

      return changed ? nextAlerts : currentAlerts;
    });
  }, []);

  // ── Fetch initial data ──
  useEffect(() => {
    fetch(`${API}/api/market-summary`)
      .then(r => r.json())
      .then(json => { 
        setData(json); 
        setLoading(false);
        evaluateAlerts(json);
      })
      .catch(() => setLoading(false));
  }, [evaluateAlerts]);

  // ── Fetch updated data every 10 seconds and check user-configured alerts ──
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API}/api/market-summary`)
        .then(r => r.json())
        .then(json => {
          setData(json);
          evaluateAlerts(json);
        })
        .catch(() => {});
    }, 10000); // Update every 10 seconds
    
    return () => clearInterval(interval);
  }, [evaluateAlerts]);

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

  const coinOptions = useMemo(() =>
    data
      .map(coin => ({
        value: coin.id,
        label: `${coin.name} (${coin.id})`,
      }))
      .sort((a, b) => a.label.localeCompare(b.label)),
    [data]
  );

  const selectedAlertCoin = useMemo(
    () => data.find(coin => coin.id === alertSymbol),
    [data, alertSymbol]
  );

  const addPriceAlert = () => {
    if (!alertSymbol || !alertPrice || Number(alertPrice) <= 0) return;

    const targetPrice = Number(alertPrice);
    const currentPrice = selectedAlertCoin?.current_price;
    const newAlert = {
      id: makeAlertId(),
      symbol: alertSymbol,
      direction: alertDirection,
      targetPrice,
      triggered: currentPrice != null
        ? isAlertTriggered({ direction: alertDirection, targetPrice }, Number(currentPrice))
        : false,
      createdAt: Date.now(),
      lastTriggeredAt: null,
    };

    setAlerts(prev => [newAlert, ...prev]);

    if (newAlert.triggered && currentPrice != null) {
      notification.warning({
        key: alertNotificationKey(newAlert),
        message: `${newAlert.symbol} đang chạm ngưỡng giá`,
        description: alertDescription(newAlert, Number(currentPrice)),
        placement: 'topRight',
        duration: 6,
      });
    }

    setAlertPrice(null);
  };

  const removePriceAlert = (id) => {
    setAlerts(prev => prev.filter(alert => alert.id !== id));
  };

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
          <div className="table-tools">
            <Button
              className="alert-button"
              icon={<BellOutlined />}
              onClick={() => setAlertOpen(true)}
            >
              Cảnh báo{alerts.length ? ` (${alerts.length})` : ''}
            </Button>
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

      <Modal
        title="Cảnh báo giá"
        open={alertOpen}
        onCancel={() => setAlertOpen(false)}
        footer={null}
        width={680}
        className="alert-modal"
      >
        <div className="alert-form">
          <Select
            showSearch
            placeholder="Chọn coin"
            value={alertSymbol}
            onChange={setAlertSymbol}
            options={coinOptions}
            optionFilterProp="label"
            className="alert-coin-select"
          />
          <Select
            value={alertDirection}
            onChange={setAlertDirection}
            options={[
              { value: 'below', label: 'Dưới hoặc bằng' },
              { value: 'above', label: 'Trên hoặc bằng' },
            ]}
            className="alert-direction-select"
          />
          <InputNumber
            min={0}
            value={alertPrice}
            onChange={setAlertPrice}
            placeholder="Giá USD"
            className="alert-price-input"
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={addPriceAlert}
            disabled={!alertSymbol || !alertPrice || Number(alertPrice) <= 0}
            className="alert-add-button"
          >
            Thêm
          </Button>
        </div>

        {selectedAlertCoin && (
          <div className="alert-current-price">
            Giá hiện tại của {selectedAlertCoin.id}: <strong>{formatPrice(selectedAlertCoin.current_price)}</strong>
          </div>
        )}

        <div className="alert-list">
          {alerts.length === 0 ? (
            <div className="alert-empty">Chưa có cảnh báo nào.</div>
          ) : alerts.map(alert => (
            <div className={`alert-row ${alert.triggered ? 'triggered' : ''}`} key={alert.id}>
              <div className="alert-rule">
                <span className="alert-symbol">{alert.symbol}</span>
                <span className="alert-threshold">
                  Giá {alert.direction === 'below' ? '≤' : '≥'} {formatPrice(alert.targetPrice)}
                </span>
              </div>
              <span className="alert-status">
                {alert.triggered ? 'Đã chạm ngưỡng' : 'Đang theo dõi'}
              </span>
              <Button
                type="text"
                icon={<DeleteOutlined />}
                onClick={() => removePriceAlert(alert.id)}
                className="alert-delete-button"
                aria-label={`Xóa cảnh báo ${alert.symbol}`}
              />
            </div>
          ))}
        </div>
      </Modal>

      <footer className="home-footer">
        <Text type="secondary" style={{ fontSize: 12 }}>
          Dữ liệu giá từ Binance · Batch Layer cập nhật mỗi 10 phút · Speed Layer real-time
        </Text>
      </footer>
    </div>
  );
}
