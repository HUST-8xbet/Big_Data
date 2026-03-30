import { useState, useEffect } from 'react'

function App() {
  // Biến lưu trữ cục dữ liệu lấy từ Backend
  const [priceData, setPriceData] = useState(null)

  // Hàm này tự động chạy 1 lần khi mở trang web
  useEffect(() => {
    // Gọi anh bồi bàn (fetch) chạy sang nhà bếp (Backend ở cổng 8000)
    fetch('http://localhost:8000/api/mock-price')
      .then(response => response.json()) // Lấy khay thức ăn (dữ liệu JSON)
      .then(data => setPriceData(data))  // Bưng lên bàn (lưu vào biến priceData)
      .catch(error => console.error("Lỗi rồi:", error))
  }, [])

  return (
    <div style={{ padding: "40px", fontFamily: "sans-serif" }}>
      <h1>Dashboard Cảnh báo Giá Crypto 🚀</h1>
      
      {/* Nếu chưa lấy được data thì hiện chữ Đang tải, nếu có rồi thì in ra */}
      {priceData ? (
        <div style={{ 
          background: "#f0f0f0", 
          padding: "20px", 
          borderRadius: "10px", 
          maxWidth: "400px" 
        }}>
          <p><strong>Đồng coin:</strong> {priceData.coin}</p>
          <p><strong>Giá thực tế:</strong> ${priceData.real_price}</p>
          <p><strong>Giá ML dự đoán:</strong> <span style={{color: "red"}}>${priceData.predicted_price}</span></p>
          <p><strong>Cập nhật lúc:</strong> {new Date(priceData.timestamp).toLocaleTimeString()}</p>
        </div>
      ) : (
        <p>Đang tải dữ liệu từ Backend...</p>
      )}
    </div>
  )
}

export default App