import json
import logging
import websocket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 1. Danh sách các cặp tiền bạn muốn theo dõi (viết thường)
COINS = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt']

# 2. Tạo đường link Combined Stream tự động
streams = '/'.join([f"{coin}@trade" for coin in COINS])
BINANCE_SOCKET = f"wss://stream.binance.com:9443/stream?streams={streams}"

def on_message(ws, message):
    try:
        raw_message = json.loads(message)
        
        # Vì dùng luồng kết hợp, dữ liệu thật nằm trong key 'data'
        data = raw_message.get('data') 
        
        if data:
            payload = {
                'symbol': data.get('s'),      # Ký hiệu (VD: BTCUSDT)
                'price': float(data.get('p')),# Giá
                'volume': float(data.get('q')),# Khối lượng
                'timestamp': data.get('E')    # Thời gian
            }
            
            # In ra màn hình với định dạng cột cho dễ nhìn
            logger.info(f"🪙 {payload['symbol']:<8} | Giá: {payload['price']:<10} | KL: {payload['volume']}")
            
    except Exception as e:
        logger.error(f"Lỗi phân tích JSON: {e}")

def on_error(ws, error): logger.error(f"Lỗi: {error}")
def on_close(ws, close_status_code, close_msg): logger.info("Đã đóng kết nối.")
def on_open(ws): logger.info(f"🟢 Đang lắng nghe các luồng: {streams}")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        BINANCE_SOCKET, on_open=on_open, on_message=on_message, 
        on_error=on_error, on_close=on_close
    )
    ws.run_forever()