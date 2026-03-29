import os
import json
import logging
import websocket
from kafka import KafkaProducer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'binance_live_prices')

# Danh sách các mã (có thể lấy từ file .env nếu muốn)
COINS = [
    'btcusdt',   # Bitcoin (Anh cả thị trường)
    'ethusdt',   # Ethereum (Nền tảng Smart Contract lớn nhất)
    'bnbusdt',   # Binance Coin (Coin của chính sàn Binance)
    'solusdt',   # Solana (Hệ sinh thái tốc độ cực cao)
    'xrpusdt',   # Ripple (Giải pháp thanh toán xuyên quốc gia)
    'adausdt',   # Cardano (Layer 1 đình đám)
    'dogeusdt',  # Dogecoin (Meme coin tỷ đô)
    'avaxusdt',  # Avalanche (Nền tảng DeFi mở rộng)
    'dotusdt',   # Polkadot (Mạng lưới kết nối các blockchain)
    'trxusdt',   # Tron (Mạng lưới chuyển USDT phổ biến nhất)
    'linkusdt',  # Chainlink (Oracle cung cấp dữ liệu số 1)
    'maticusdt', # Polygon (Giải pháp mở rộng cho Ethereum)
    'shibusdt',  # Shiba Inu (Meme coin hệ chó phổ biến thứ 2)
    'ltcusdt',   # Litecoin (Được ví như "Bạc" so với "Vàng" BTC)
    'bchusdt',   # Bitcoin Cash (Bản phân nhánh của Bitcoin)
    'nearusdt',  # NEAR Protocol (Hệ sinh thái rất mạnh về công nghệ)
    'uniusdt',   # Uniswap (Đồng coin của sàn giao dịch phi tập trung Top 1)
    'atomusdt',  # Cosmos (Mệnh danh là Internet of Blockchains)
    'tonusdt',   # Toncoin (Đồng coin gắn liền với hệ sinh thái Telegram)
    'xlmusdt'    # Stellar (Mạng lưới thanh toán chi phí siêu rẻ)
]
streams = '/'.join([f"{coin}@trade" for coin in COINS])
BINANCE_SOCKET = f"wss://stream.binance.com:9443/stream?streams={streams}"

try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        retries=3
    )
    logger.info(f"Đã kết nối Kafka tại {KAFKA_BROKER}")
except Exception as e:
    logger.error(f"Lỗi kết nối Kafka: {e}")
    exit(1)

def on_message(ws, message):
    try:
        raw_message = json.loads(message)
        data = raw_message.get('data') # Lấy lõi dữ liệu
        
        if data:
            payload = {
                'symbol': data.get('s'),
                'price': float(data.get('p')),
                'volume': float(data.get('q')),
                'timestamp': data.get('E')
            }
            
            # Đẩy vào chung 1 topic Kafka
            producer.send(KAFKA_TOPIC, value=payload)
            logger.info(f"[KAFKA] {payload['symbol']:<8} | Giá: {payload['price']}")
            
    except Exception as e:
        logger.error(f"Lỗi xử lý dữ liệu: {e}")

def on_error(ws, error): logger.error(f"Lỗi Websocket: {error}")
def on_close(ws, close_status_code, close_msg):
    logger.warning("Đang đóng. Bắt đầu xả (flush) dữ liệu vào Kafka...")
    producer.flush()
    producer.close()
def on_open(ws): logger.info(f" Đã kết nối. Đang lấy dữ liệu {len(COINS)} mã...")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        BINANCE_SOCKET, on_open=on_open, on_message=on_message,
        on_error=on_error, on_close=on_close
    )
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        ws.close()