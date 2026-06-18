import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Input,
  InputNumber,
  Modal,
  notification,
  Select,
  Table,
  Tag,
  Typography,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  YAxis,
} from 'recharts';
import {
  BarChartOutlined,
  BellOutlined,
  DeleteOutlined,
  DollarOutlined,
  FallOutlined,
  PlusOutlined,
  RiseOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import '../styles/Home.css';

const { Title, Text } = Typography;
const { Search } = Input;

// ── Configuration ────────────────────────────────────────────────────────────
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ALERTS_STORAGE_KEY = 'cryptowatch_price_alerts';

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatPrice(price) {
  if (price == null) return '–';

  const numericPrice = Number(price);
  const absolutePrice = Math.abs(numericPrice);
  const fractionDigits =
    absolutePrice >= 100 ? 2 :
    absolutePrice >= 1 ? 4 :
    absolutePrice >= 0.01 ? 6 :
    8;

  return '$' + Number(price).toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function formatPercentage(value) {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${Number(value).toFixed(2)}%`;
}

function createAlertId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function hasAlertReachedTarget(alert, currentPrice) {
  return alert.direction === 'below'
    ? currentPrice <= alert.targetPrice
    : currentPrice >= alert.targetPrice;
}

function getAlertDescription(alert, currentPrice) {
  const directionText = alert.direction === 'below' ? 'dưới hoặc bằng' : 'trên hoặc bằng';
  return `Giá hiện tại ${formatPrice(currentPrice)} đã ${directionText} ${formatPrice(alert.targetPrice)}`;
}

function getAlertNotificationKey(alert) {
  return `price-alert-${alert.id}`;
}

// ── Mini Sparkline ───────────────────────────────────────────────────────────
function Sparkline({ data: priceValues, positive: isPositive }) {
  const chartData = priceValues.map((value, index) => ({ v: value, i: index }));
  const lineColor = isPositive ? '#00e396' : '#ff4d4f';
  const referenceValue = priceValues[0] ?? 0;

  return (
    <div className="sparkline-wrap">
      <ResponsiveContainer width="100%" height={40}>
        <LineChart data={chartData}>
          <YAxis domain={['dataMin', 'dataMax']} hide />
          <ReferenceLine
            y={referenceValue}
            stroke="rgba(255,255,255,0.1)"
            strokeDasharray="3 3"
          />
          <Line
            type="monotone"
            dataKey="v"
            stroke={lineColor}
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
  const [currentTime, setCurrentTime] = useState(() => new Date());

  useEffect(() => {
    const clockIntervalId = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(clockIntervalId);
  }, []);

  const formatTime = (timeZone) => currentTime.toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone,
  });

  return (
    <div className="header-clock">
      <div className="clock-item">
        <span className="clock-label">Việt Nam</span>
        <span className="clock-value">{formatTime('Asia/Ho_Chi_Minh')}</span>
      </div>
      <div className="clock-divider" />
      <div className="clock-item">
        <span className="clock-label">UTC</span>
        <span className="clock-value">{formatTime('UTC')}</span>
      </div>
    </div>
  );
}

// ── Market Summary Stats ─────────────────────────────────────────────────────
function MarketStats({ data: marketData }) {
  const trackedCoinCount = marketData.length;
  const gainerCount = marketData.filter(
    coin => coin.price_change_percentage_24h > 0,
  ).length;
  const loserCount = marketData.filter(
    coin => coin.price_change_percentage_24h < 0,
  ).length;
  const averageChange = marketData.length
    ? marketData.reduce(
      (totalChange, coin) => totalChange + coin.price_change_percentage_24h,
      0,
    ) / trackedCoinCount
    : 0;

  return (
    <div className="market-stats">
      <div className="mstat-card">
        <div className="mstat-icon-wrap">
          <BarChartOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{trackedCoinCount}</span>
          <span className="mstat-label">Coin theo dõi</span>
        </div>
      </div>
      <div className="mstat-card up">
        <div className="mstat-icon-wrap">
          <RiseOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{gainerCount}</span>
          <span className="mstat-label">Tăng giá</span>
        </div>
      </div>
      <div className="mstat-card down">
        <div className="mstat-icon-wrap">
          <FallOutlined className="mstat-icon" />
        </div>
        <div>
          <span className="mstat-value">{loserCount}</span>
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
            style={{ color: averageChange >= 0 ? '#00e396' : '#ff4d4f' }}
          >
            {formatPercentage(averageChange)}
          </span>
          <span className="mstat-label">Biến động TB</span>
        </div>
      </div>
    </div>
  );
}

// ── Home ──────────────────────────────────────────────────────────────────────
export default function Home() {
  const [marketData, setMarketData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [minimumPrice, setMinimumPrice] = useState(null);
  const [maximumPrice, setMaximumPrice] = useState(null);
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [selectedAlertSymbol, setSelectedAlertSymbol] = useState(null);
  const [selectedAlertDirection, setSelectedAlertDirection] = useState('below');
  const [alertTargetPrice, setAlertTargetPrice] = useState(null);
  const [priceAlerts, setPriceAlerts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(ALERTS_STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  });
  const navigate = useNavigate();

  useEffect(() => {
    localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(priceAlerts));
  }, [priceAlerts]);

  const evaluatePriceAlerts = useCallback((latestMarketData) => {
    const coinBySymbol = new Map(latestMarketData.map(coin => [coin.id, coin]));

    setPriceAlerts(currentAlerts => {
      let hasChanges = false;

      const nextAlerts = currentAlerts.map(alert => {
        const coin = coinBySymbol.get(alert.symbol);
        if (!coin || coin.current_price == null) return alert;

        const currentPrice = Number(coin.current_price);
        const isTriggered = hasAlertReachedTarget(alert, currentPrice);
        const wasTriggered = Boolean(alert.triggered);

        if (isTriggered && !wasTriggered) {
          notification.warning({
            key: getAlertNotificationKey(alert),
            message: `${alert.symbol} chạm ngưỡng giá`,
            description: getAlertDescription(alert, currentPrice),
            placement: 'topRight',
            duration: 6,
          });
        }

        if (isTriggered !== wasTriggered) {
          hasChanges = true;
          return {
            ...alert,
            triggered: isTriggered,
            lastTriggeredAt: isTriggered ? Date.now() : alert.lastTriggeredAt,
          };
        }

        return alert;
      });

      return hasChanges ? nextAlerts : currentAlerts;
    });
  }, []);

  // ── Initial market data ───────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/market-summary`)
      .then(response => response.json())
      .then(latestMarketData => {
        setMarketData(latestMarketData);
        setIsLoading(false);
        evaluatePriceAlerts(latestMarketData);
      })
      .catch(() => setIsLoading(false));
  }, [evaluatePriceAlerts]);

  // ── Market polling and price-alert evaluation ─────────────────────────────
  useEffect(() => {
    const marketPollingIntervalId = setInterval(() => {
      fetch(`${API_BASE_URL}/api/market-summary`)
        .then(response => response.json())
        .then(latestMarketData => {
          setMarketData(latestMarketData);
          evaluatePriceAlerts(latestMarketData);
        })
        .catch(() => {});
    }, 10000);

    return () => clearInterval(marketPollingIntervalId);
  }, [evaluatePriceAlerts]);

  const filteredMarketData = useMemo(
    () => marketData.filter(coin => {
      const normalizedSearchQuery = searchQuery.toLowerCase();
      const matchesSearch =
        coin.name.toLowerCase().includes(normalizedSearchQuery) ||
        coin.symbol.toLowerCase().includes(normalizedSearchQuery);

      const coinPrice = coin.current_price;
      const meetsMinimumPrice =
        minimumPrice === null || coinPrice >= minimumPrice;
      const meetsMaximumPrice =
        maximumPrice === null || coinPrice <= maximumPrice;

      return matchesSearch && meetsMinimumPrice && meetsMaximumPrice;
    }),
    [marketData, searchQuery, minimumPrice, maximumPrice],
  );

  const alertCoinOptions = useMemo(
    () => marketData
      .map(coin => ({
        value: coin.id,
        label: `${coin.name} (${coin.id})`,
      }))
      .sort((a, b) => a.label.localeCompare(b.label)),
    [marketData],
  );

  const selectedAlertCoin = useMemo(
    () => marketData.find(coin => coin.id === selectedAlertSymbol),
    [marketData, selectedAlertSymbol],
  );

  const addPriceAlert = () => {
    if (
      !selectedAlertSymbol ||
      !alertTargetPrice ||
      Number(alertTargetPrice) <= 0
    ) {
      return;
    }

    const targetPrice = Number(alertTargetPrice);
    const currentPrice = selectedAlertCoin?.current_price;
    const newAlert = {
      id: createAlertId(),
      symbol: selectedAlertSymbol,
      direction: selectedAlertDirection,
      targetPrice,
      triggered: currentPrice != null
        ? hasAlertReachedTarget(
          { direction: selectedAlertDirection, targetPrice },
          Number(currentPrice),
        )
        : false,
      createdAt: Date.now(),
      lastTriggeredAt: null,
    };

    setPriceAlerts(currentAlerts => [newAlert, ...currentAlerts]);

    if (newAlert.triggered && currentPrice != null) {
      notification.warning({
        key: getAlertNotificationKey(newAlert),
        message: `${newAlert.symbol} đang chạm ngưỡng giá`,
        description: getAlertDescription(newAlert, Number(currentPrice)),
        placement: 'topRight',
        duration: 6,
      });
    }

    setAlertTargetPrice(null);
  };

  const removePriceAlert = (alertId) => {
    setPriceAlerts(currentAlerts =>
      currentAlerts.filter(alert => alert.id !== alertId),
    );
  };

  const tableColumns = [
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
      render: (price) => (
        <Text strong style={{ color: '#e8e8e8', fontFamily: 'var(--mono)' }}>
          {formatPrice(price)}
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
      render: (percentageChange) => {
        const isPositive = percentageChange >= 0;

        return (
          <Tag
            color={isPositive ? 'green' : 'red'}
            style={{
              borderRadius: 20,
              fontWeight: 600,
              minWidth: 72,
              textAlign: 'center',
              justifyContent: 'center',
            }}
          >
            {isPositive ? <RiseOutlined /> : <FallOutlined />}
            {' '}{formatPercentage(percentageChange)}
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
      render: (priceValues, record) => (
        <Sparkline
          data={priceValues}
          positive={record.price_change_percentage_24h >= 0}
        />
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
      <MarketStats data={marketData} />

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
              onClick={() => setIsAlertModalOpen(true)}
            >
              Cảnh báo{priceAlerts.length ? ` (${priceAlerts.length})` : ''}
            </Button>
            <Search
              placeholder="Tìm coin (BTC, ETH, SOL...)"
              allowClear
              prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
              onChange={event => setSearchQuery(event.target.value)}
              className="search-input"
            />
            <InputNumber
              placeholder="Giá tối thiểu"
              min={0}
              value={minimumPrice}
              onChange={setMinimumPrice}
              style={{ width: 140 }}
            />
            <span style={{ color: '#6b7280' }}>—</span>
            <InputNumber
              placeholder="Giá tối đa"
              min={0}
              value={maximumPrice}
              onChange={setMaximumPrice}
              style={{ width: 140 }}
            />
          </div>
        </div>

        <Table
          columns={tableColumns}
          dataSource={filteredMarketData}
          rowKey="id"
          loading={isLoading}
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
        open={isAlertModalOpen}
        onCancel={() => setIsAlertModalOpen(false)}
        footer={null}
        width={680}
        className="alert-modal"
      >
        <div className="alert-form">
          <Select
            showSearch
            placeholder="Chọn coin"
            value={selectedAlertSymbol}
            onChange={setSelectedAlertSymbol}
            options={alertCoinOptions}
            optionFilterProp="label"
            className="alert-coin-select"
          />
          <Select
            value={selectedAlertDirection}
            onChange={setSelectedAlertDirection}
            options={[
              { value: 'below', label: 'Dưới hoặc bằng' },
              { value: 'above', label: 'Trên hoặc bằng' },
            ]}
            className="alert-direction-select"
          />
          <InputNumber
            min={0}
            value={alertTargetPrice}
            onChange={setAlertTargetPrice}
            placeholder="Giá USD"
            className="alert-price-input"
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={addPriceAlert}
            disabled={
              !selectedAlertSymbol ||
              !alertTargetPrice ||
              Number(alertTargetPrice) <= 0
            }
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
          {priceAlerts.length === 0 ? (
            <div className="alert-empty">Chưa có cảnh báo nào.</div>
          ) : priceAlerts.map(alert => (
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
