import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function CoinDetail() {
  // 1. TÓM LẤY TÊN COIN TỪ URL
  const { symbol } = useParams(); 
  
  // Đảm bảo tên coin luôn viết hoa (VD: "btcusdt" trên URL -> "BTCUSDT") để khớp với backend
  const currentCoin = symbol ? symbol.toUpperCase() : "BTCUSDT"; 
  
  // Khởi tạo hàm chuyển trang để làm nút "Quay lại"
  const navigate = useNavigate();

  const [priceData, setPriceData] = useState([])
  const [wsStatus, setWsStatus] = useState("🟡 Đang kết nối...")

  // 2. LẤY DỮ LIỆU LỊCH SỬ (Chạy lại khi currentCoin thay đổi)
  useEffect(() => {
    setPriceData([]); 
    setWsStatus("🟡 Đang lấy dữ liệu " + currentCoin + "...");

    // THAY selectedCoin BẰNG currentCoin
    fetch(`http://127.0.0.1:8000/api/historical-price/${currentCoin}`)
      .then(response => response.json())
      .then(data => setPriceData(data))
      .catch(error => {
        console.error("Lỗi lấy lịch sử:", error);
        setWsStatus("🔴 Lỗi lấy dữ liệu lịch sử");
      })
  }, [currentCoin]) 

  // 3. KẾT NỐI WEBSOCKET
  useEffect(() => {
    let isMounted = true; 
    
    // THAY selectedCoin BẰNG currentCoin
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/live-price/${currentCoin}`);

    ws.onopen = () => {
      if (isMounted) setWsStatus("🟢 Trực tiếp (Real-time)");
    };

    ws.onmessage = (event) => {
        if (!isMounted) return; 
        const newDataPoint = JSON.parse(event.data);
        
        setPriceData(prevData => {
          // Nếu chưa có dữ liệu, thêm mới
          if (prevData.length === 0) return [newDataPoint];
          
          // Cập nhật mảng mới
          const updatedData = [...prevData, newDataPoint];
          
          // Tăng giới hạn lưu trữ lên 500 điểm (hoặc tùy bạn) để không bị mất đoạn cũ
          return updatedData.length > 500 ? updatedData.slice(1) : updatedData;
        });
      };

    ws.onerror = () => {
      if (isMounted) setWsStatus("🔴 Lỗi đường truyền WebSocket");
    };

    ws.onclose = () => {
      if (isMounted) setWsStatus("🔴 Mất kết nối với Server");
    };

    return () => {
      isMounted = false; 
      ws.close(); 
    };
  }, [currentCoin]); 

  return (
    <div style={{ padding: "40px", fontFamily: "sans-serif", backgroundColor: "#f8f9fa", minHeight: "100vh" }}>
      
      {/* KHU VỰC HEADER (Đã bỏ thẻ select, thêm nút Quay lại) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <button 
          onClick={() => navigate('/')} 
          style={{ padding: "10px 20px", cursor: "pointer", borderRadius: "8px", border: "1px solid #ccc", backgroundColor: "white", fontWeight: "bold" }}
        >
          ⬅ Quay lại Bảng giá
        </button>

        <h1 style={{ color: "#333", margin: 0 }}>
          Biểu đồ phân tích: <span style={{ color: "#007bff" }}>{currentCoin}</span>
        </h1>

        <div style={{ width: "120px" }}></div> {/* Thẻ div rỗng để căn giữa thẻ h1 */}
      </div>
      
      <h3 style={{ textAlign: "center", color: wsStatus.includes("🟢") ? "green" : (wsStatus.includes("🔴") ? "red" : "#d39e00") }}>
        {wsStatus}
      </h3>
      
      {/* KHU VỰC BIỂU ĐỒ */}
      <div style={{ backgroundColor: "white", padding: "20px", borderRadius: "15px", boxShadow: "0 4px 6px rgba(0,0,0,0.1)", height: "500px", marginTop: "20px"}}>
        {priceData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={priceData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.5} />
              <XAxis dataKey="time" />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="real_price" name="Giá Thực Tế ($)" stroke="#28a745" strokeWidth={3} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="predicted_price" name="AI Dự Đoán ($)" stroke="#fd7e14" strokeWidth={2} strokeDasharray="5 5" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <h3 style={{ textAlign: "center", marginTop: "200px", color: "#888" }}>Đang tải biểu đồ...</h3>
        )}
      </div>
    </div>
  )
}

export default CoinDetail