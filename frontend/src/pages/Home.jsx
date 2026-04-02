import React, { useState, useEffect } from 'react';
import { Table, Typography, Tag, Space, Input } from 'antd';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';

const { Title } = Typography;
const { Search } = Input;

export default function Home() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/market-summary')
      .then(res => res.json())
      .then(json => {
        setData(json);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const columns = [
    {
      title: 'Tên Coin',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <strong>{text}</strong>
          <span style={{ color: 'gray' }}>{record.symbol.toUpperCase()}</span>
        </Space>
      ),
    },
    {
      title: 'Giá (USD)',
      dataIndex: 'current_price',
      key: 'current_price',
      sorter: (a, b) => a.current_price - b.current_price,
      render: (price) => `$${price.toLocaleString()}`,
    },
    {
      title: 'Biến động 2h',
      dataIndex: 'price_change_percentage_24h',
      key: 'change',
      sorter: (a, b) => a.price_change_percentage_24h - b.price_change_percentage_24h,
      render: (change) => {
        const color = change >= 0 ? 'success' : 'error';
        return <Tag color={color}>{change > 0 ? '+' : ''}{change.toFixed(2)}%</Tag>;
      },
    },
    {
      title: 'Xu hướng',
      dataIndex: 'sparkline',
      key: 'sparkline',
      render: (sparklineData, record) => {
        if (!sparklineData || sparklineData.length === 0) return null;
        const chartData = sparklineData.map((val, index) => ({ price: val, index }));
        const lineColor = record.price_change_percentage_24h >= 0 ? '#52c41a' : '#ff4d4f';

        return (
          <div style={{ width: 120, height: 40 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <YAxis domain={['dataMin', 'dataMax']} hide />
                <Line
                  type="linear"
                  dataKey="price"
                  stroke={lineColor}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      }
    }
  ];

  const filteredData = data.filter(coin =>
    coin.name.toLowerCase().includes(searchText.toLowerCase()) ||
    coin.symbol.toLowerCase().includes(searchText.toLowerCase())
  );

  return (
    <div style={{ padding: '40px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <Title level={2} style={{ margin: 0 }}>Thị trường Crypto</Title>
        <Search
          placeholder="Tìm kiếm coin (VD: BTC, ETH...)"
          allowClear
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 300 }}
        />
      </div>
      
      <Table
        columns={columns}
        dataSource={filteredData}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        onRow={(record) => {
          return {
            onClick: () => {
              navigate(`/coin/${record.symbol}`);
            },
            style: { cursor: 'pointer' }
          };
        }}
      />
    </div>
  );
}