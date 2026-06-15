#!/usr/bin/env python3
"""
Train LSTM trực tiếp từ file training_data.npz (không cần InfluxDB).
Dùng trên server có GPU sau khi đã scp file training_data.npz lên.

Chạy: python train_from_file.py
"""

import numpy as np
from ml_service import train_model_on_historical_data
import warnings

warnings.simplefilter("ignore")

DATA_FILE = "training_data.npz"


def main():
    print("=" * 60)
    print("🤖 LSTM Model Training Script (from file)")
    print("=" * 60)

    print(f"📂 Đang đọc {DATA_FILE}...")
    data = np.load(DATA_FILE)
    historical_data = {symbol: data[symbol] for symbol in data.files}

    print("\n📈 Thống kê dữ liệu:")
    for symbol, prices in historical_data.items():
        print(f"  {symbol}: {len(prices)} điểm")
    print(f"\n✅ Tổng cộng {len(historical_data)} coin")

    print("\n🔧 Đang huấn luyện mô hình LSTM...")
    train_model_on_historical_data(historical_data)

    print("\n" + "=" * 60)
    print("✅ Huấn luyện hoàn tất! model.pt đã sẵn sàng.")
    print("💡 Tải model.pt về máy local: scp user@server:~/Big_Data/backend/model.pt ./backend/")
    print("=" * 60)


if __name__ == "__main__":
    main()
