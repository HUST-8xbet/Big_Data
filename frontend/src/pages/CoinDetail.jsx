import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Select, Spin, Tag, Typography } from 'antd';
import {
  ArrowLeftOutlined,
  FallOutlined,
  InfoCircleOutlined,
  RiseOutlined,
  SwapOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import '../styles/CoinDetail.css';

const { Text } = Typography;
const { Option } = Select;

// ── Configuration ────────────────────────────────────────────────────────────
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Time ranges (minutes) ────────────────────────────────────────────────────
const TIME_RANGES = [
  { label: '15 phút', value: 15 },
  { label: '30 phút', value: 30 },
  { label: '1 giờ', value: 60 },
  { label: '2 giờ', value: 120 },
  { label: '4 giờ', value: 240 },
];

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

  return '$' + numericPrice.toLocaleString('en-US', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

function calculatePriceChange(priceData) {
  if (!priceData || priceData.length < 2) {
    return { pct: 0, icon: null, color: '#9ca3af' };
  }

  const firstPrice = priceData[0].real_price;
  const latestPrice = priceData[priceData.length - 1].real_price;
  const percentage = ((latestPrice - firstPrice) / firstPrice) * 100;
  const icon = percentage >= 0 ? <RiseOutlined /> : <FallOutlined />;
  const color =
    percentage > 0 ? '#52c41a' :
    percentage < 0 ? '#ff4d4f' :
    '#9ca3af';

  return { pct: percentage, icon, color };
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="chart-tooltip">
      <div className="tooltip-time">{label}</div>
      {payload.map((dataPoint) => (
        <div key={dataPoint.dataKey} className="tooltip-row">
          <span
            className="tooltip-dot"
            style={{ background: dataPoint.color }}
          />
          <span className="tooltip-label">{dataPoint.name}</span>
          <span
            className="tooltip-value"
            style={{ color: dataPoint.color }}
          >
            {formatPrice(dataPoint.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── CoinDetail Component ──────────────────────────────────────────────────────
export default function CoinDetail() {
  const { symbol: routeSymbol } = useParams();
  const navigate = useNavigate();

  // Đảm bảo symbol luôn viết hoa (VD: "btc" → "BTC")
  const [selectedSymbol, setSelectedSymbol] = useState(
    routeSymbol ? routeSymbol.toUpperCase() : 'BTCUSDT',
  );
  const [availableSymbols, setAvailableSymbols] = useState([]);

  // Dữ liệu
  const [rawPriceData, setRawPriceData] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [forecastData, setForecastData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTimeRange, setSelectedTimeRange] = useState(60);

  // Chế độ lịch sử được bật khi người dùng kéo Brush khỏi điểm dữ liệu mới nhất.
  const [isHistoryMode, setIsHistoryMode] = useState(false);
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  // ── 1. Lấy danh sách coin từ market-summary ──────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/market-summary`)
      .then(response => response.json())
      .then(marketData => setAvailableSymbols(marketData.map(coin => coin.id)))
      .catch(() => {});
  }, []);

  // ── 2. Fetch lịch sử ──────────────────────────────────────────────────────
  const fetchPriceHistory = useCallback((
    symbol,
    minutes,
    { silent = false } = {},
  ) => {
    if (!silent) {
      setIsLoading(true);
      setRawPriceData([]);
      setChartData([]);
      setIsHistoryMode(false);
    }

    let aggregationInterval = '1m';
    if (minutes >= 240) aggregationInterval = '5m';
    else if (minutes >= 120) aggregationInterval = '3m';
    else if (minutes >= 60) aggregationInterval = '2m';

    fetch(`${API_BASE_URL}/api/historical-price/${symbol}?minutes=${minutes}&interval=${aggregationInterval}`)
      .then(response => response.json())
      .then(historyData => {
        if (!historyData.length) {
          setIsLoading(false);
          setIsLiveConnected(false);
          return;
        }

        const enrichedHistoryData = historyData.map((dataPoint, index) => ({
          ...dataPoint,
          _index: index,
          displayTime: dataPoint.time,
        }));

        setRawPriceData(enrichedHistoryData);
        setIsLiveConnected(true);
        setIsLoading(false);
      })
      .catch(error => {
        console.error('Lỗi fetch lịch sử:', error);
        setIsLiveConnected(false);
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchPriceHistory(selectedSymbol, selectedTimeRange);
  }, [selectedSymbol, selectedTimeRange, fetchPriceHistory]);

  // Poll nến 1 phút. Không clear chart để tránh nhấp nháy/giật viewport.
  useEffect(() => {
    const historyPollingIntervalId = setInterval(() => {
      if (!isHistoryMode) {
        fetchPriceHistory(selectedSymbol, selectedTimeRange, { silent: true });
      }
    }, 60000);

    return () => clearInterval(historyPollingIntervalId);
  }, [
    selectedSymbol,
    selectedTimeRange,
    isHistoryMode,
    fetchPriceHistory,
  ]);

  // ── 3. Fetch dự đoán tương lai, làm mới mỗi 60 giây ───────────────────────
  const fetchPriceForecast = useCallback((symbol) => {
    fetch(`${API_BASE_URL}/api/forecast/${symbol}?steps=15`)
      .then(response => response.json())
      .then(forecastResponse => {
        setForecastData(forecastResponse.map(dataPoint => ({
          displayTime: dataPoint.time,
          predicted_price: dataPoint.predicted_price,
          isAnchor: Boolean(dataPoint.anchor),
          isForecast: true,
        })));
      })
      .catch(() => setForecastData([]));
  }, []);

  useEffect(() => {
    setForecastData([]);
    fetchPriceForecast(selectedSymbol);

    const forecastPollingIntervalId = setInterval(
      () => fetchPriceForecast(selectedSymbol),
      60000,
    );

    return () => clearInterval(forecastPollingIntervalId);
  }, [selectedSymbol, fetchPriceForecast]);

  // Giữ riêng hai lớp state để bảo toàn vòng đời render hiện tại.
  useEffect(() => {
    setChartData(rawPriceData);
  }, [rawPriceData]);

  // ── Derived chart values ──────────────────────────────────────────────────
  const priceChange = calculatePriceChange(chartData);
  const historicalPrices = chartData
    .map(dataPoint => dataPoint.real_price)
    .filter(Boolean);
  const highestPrice = historicalPrices.length
    ? Math.max(...historicalPrices)
    : null;
  const lowestPrice = historicalPrices.length
    ? Math.min(...historicalPrices)
    : null;

  // Lịch sử và dự đoán tương lai được nối tại điểm dữ liệu mới nhất.
  const isLive = !isHistoryMode;
  const currentPrice = chartData.length
    ? chartData[chartData.length - 1].real_price
    : null;
  const currentTime = chartData.length
    ? chartData[chartData.length - 1].displayTime
    : null;
  const futureForecastData = useMemo(
    () => (
      forecastData[0]?.isAnchor ? forecastData.slice(1) : forecastData
    ),
    [forecastData],
  );

  const historicalDisplayData = useMemo(
    () => chartData.map((dataPoint, index) => ({
      ...dataPoint,
      // Chỉ nối đường dự đoán vào điểm giá thực tế cuối cùng.
      predicted_price:
        index === chartData.length - 1 && forecastData.length > 0
          ? dataPoint.real_price
          : null,
    })),
    [chartData, forecastData.length],
  );

  const displayData = useMemo(
    () => (
      chartData.length
        ? [...historicalDisplayData, ...futureForecastData]
        : chartData
    ),
    [chartData, historicalDisplayData, futureForecastData],
  );

  const yAxisDomain = useMemo(() => {
    const visiblePrices = displayData
      .flatMap(dataPoint => [
        dataPoint.real_price,
        dataPoint.predicted_price,
      ])
      .filter(price => price != null);

    if (!visiblePrices.length) return ['auto', 'auto'];

    const minimumVisiblePrice = Math.min(...visiblePrices);
    const maximumVisiblePrice = Math.max(...visiblePrices);
    const domainPadding = Math.max(
      (maximumVisiblePrice - minimumVisiblePrice) * 0.08,
      Math.abs(maximumVisiblePrice || 1) * 0.0005,
    );

    return [
      minimumVisiblePrice - domainPadding,
      maximumVisiblePrice + domainPadding,
    ];
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
            value={selectedSymbol}
            onChange={symbol => setSelectedSymbol(symbol)}
            className="coin-selector"
            popupClassName="coin-selector-dropdown"
            suffixIcon={<SwapOutlined />}
          >
            {availableSymbols.map(symbol => (
              <Option key={symbol} value={symbol}>{symbol}</Option>
            ))}
          </Select>

          <div className="live-badge" data-live={isLive}>
            <span className="live-dot" />
            {isLive ? 'Trực tiếp' : 'Lịch sử'}
          </div>
        </div>

        <div className="header-status">
          <Tag
            color={isLiveConnected ? 'green' : 'red'}
            icon={<ThunderboltOutlined />}
          >
            {isLiveConnected ? 'Live: On' : 'Live: Syncing'}
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
          <span className="stat-label">Cao nhất ({TIME_RANGES.find(t => t.value === selectedTimeRange)?.label})</span>
          <span className="stat-value up">{formatPrice(highestPrice)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Thấp nhất ({TIME_RANGES.find(t => t.value === selectedTimeRange)?.label})</span>
          <span className="stat-value down">{formatPrice(lowestPrice)}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Biến động</span>
          <span className="stat-value" style={{ color: priceChange.color }}>
            {priceChange.icon} {priceChange.pct >= 0 ? '+' : ''}{priceChange.pct.toFixed(2)}%
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
            {TIME_RANGES.map(timeRangeOption => (
              <button
                key={timeRangeOption.value}
                className={`range-btn ${selectedTimeRange === timeRangeOption.value && isLive ? 'active' : ''}`}
                onClick={() => setSelectedTimeRange(timeRangeOption.value)}
              >
                {timeRangeOption.label}
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
          {isLoading ? (
            <div className="chart-loading">
              <Spin size="large" />
              <Text type="secondary">Đang tải dữ liệu...</Text>
            </div>
          ) : displayData.length === 0 ? (
            <div className="chart-loading">
              <InfoCircleOutlined style={{ fontSize: 32, color: '#9ca3af' }} />
              <Text type="secondary">Không có dữ liệu cho {selectedSymbol}</Text>
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
                  domain={yAxisDomain}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={axisPrice => formatPrice(axisPrice)}
                  width={90}
                />
                <Tooltip content={<CustomTooltip />} />

                {/* Đường kẻ dọc "Bây giờ" — bên phải là dự đoán tương lai */}
                {currentTime && forecastData.length > 0 && (
                  <ReferenceLine
                    x={currentTime}
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
          {selectedSymbol} · Dữ liệu từ InfluxDB · Batch Layer cập nhật mỗi 10 phút
        </Text>
      </footer>
    </div>
  );
}
