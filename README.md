# 🤖 Crypto Trading Assistant

Bot tự động phát hiện tích luỹ và breakout trên thị trường crypto với phân tích đa khung thời gian (multi-timeframe).

[![Deploy to Fly.io](https://img.shields.io/badge/Deploy-Fly.io-blueviolet)](https://fly.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ Tính năng

### 📊 Phân tích kỹ thuật
- ✅ **Multi-timeframe analysis**: 5m, 15m, 30m, 1h
- ✅ **Tích luỹ (Accumulation)**: Phát hiện zone tích luỹ tự động
- ✅ **Breakout detection**: Xác nhận breakout với volume
- ✅ **Higher TF confirmation**: Xác nhận với khung thời gian cao hơn

### 🎯 Gợi ý giao dịch
- ✅ **TP/SL thông minh**: Hybrid approach (Zone + ATR + R:R 1:2)
- ✅ **Risk level**: Cao/Trung bình/Thấp theo timeframe
- ✅ **Hold time**: < 4h → 3 ngày tùy setup
- ✅ **Volume confirmation**: Lọc false breakout

### 📱 Thông báo Telegram
- ✅ Phát hiện tích luỹ
- ✅ Breakout alerts với setup chi tiết
- ✅ Format đẹp, dễ đọc trên mobile

---

## 🚀 Quick Start

### 1. Clone repository
```bash
git clone https://github.com/QuanPink/CryptoTradingAssitant.git
cd crypto-trading-assistant
```

### 2. Setup môi trường
```bash
# Tạo virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Cấu hình
```bash
# Copy file example
cp .env.example .env

# Edit .env với thông tin của bạn
nano .env
```

**Required config:**
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Symbols to monitor
SYMBOLS=BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT

# Timeframes
TIMEFRAMES=5m,15m,30m,1h
```

### 4. Chạy bot
```bash
python main.py
```

---

## 🐳 Deploy với Docker

### Local
```bash
# Build image
docker build -t crypto-bot .

# Run container
docker run -d \
  --name crypto-bot \
  --env-file .env \
  crypto-bot
```

### Fly.io (Production)
```bash
# Login
flyctl auth login

# Deploy
flyctl deploy

# View logs
flyctl logs -f
```

---

## 📊 Ví dụ Notification

### 💤 Tích luỹ
```
💤 PHÁT HIỆN TÍCH LUỸ
━━━━━━━━━━━━━━━━━━

🪙 BTC/USDT
⏱ ⚡ Scalping (5 phút)

💰 Giá: 70,150.00
🔴 Kháng cự: 70,400.00
🟢 Hỗ trợ: 69,900.00

📊 Độ rộng 0.71% • Vị trí 50%
⏳ Tích luỹ 2.0h • 🟡 Trung bình

━━━━━━━━━━━━━━━━━━
📋 Risk Cao • SL 0.3-0.8%
⏱ Hold: < 4h
```

### 🚀 Breakout
```
🚀 BREAKOUT TĂNG
━━━━━━━━━━━━━━━━━━

🪙 BTC/USDT
⏱ ⚡ Scalping (5 phút)

💰 Giá: 70,500.00
🎯 Kháng cự: 70,300.00
📈 Breakout: 0.28%

📦 Volume: x2.5 ✅
✅ Confirm TF cao hơn
━━━━━━━━━━━━━━━━━━
🎯 GỢI Ý SETUP

📍 Entry: 70,500.00
🛑 SL: 69,800.00 (-0.99%)
🎯 TP: 71,900.00 (+1.99%)
📊 R:R = 1:2

⏱ < 4h • Risk Cao

✅ Setup chất lượng cao
⚠️ Tự kiểm tra trước khi vào
```

---

## ⚙️ Cấu hình

### Exchange
```bash
EXCHANGE_ID=binance          # Exchange (binance, bybit, etc)
SYMBOLS=BTC/USDT,ETH/USDT   # Symbols to monitor
TIMEFRAMES=5m,15m,30m,1h    # Timeframes to analyze
```

### Thresholds
```bash
ATR_RATIO_THRESHOLD=0.002       # ATR < 0.2% → Low volatility
VOL_RATIO_THRESHOLD=0.7         # Volume < 70% avg → Low volume
PRICE_RANGE_THRESHOLD=0.008     # Range < 0.8% → Tight range
VOL_SPIKE_MULTIPLIER=1.5        # Volume > 1.5x avg → Spike
```

### Cooldowns
```bash
ACCUMULATION_COOLDOWN_MIN=60    # 1h giữa accumulation notifications
BREAKOUT_COOLDOWN_MIN=60        # 1h giữa breakout notifications
ZONE_EXPIRE_HOURS=12            # Zone expire sau 12h
```

---

## 🏗️ Cấu trúc Project
```
crypto-trading-assistant/
├── main.py                    # Entry point
├── health.py                  # Health check endpoint
├── requirements.txt           # Dependencies
├── Dockerfile                 # Docker config
├── fly.toml                   # Fly.io config
├── .env.example              # Environment variables template
├── config/
│   └── setting.py            # Settings management
├── src/
│   ├── analyzers/
│   │   └── accumulation.py   # Accumulation detection logic
│   ├── indicators/
│   │   └── technical.py      # Technical indicators (ATR, BBW)
│   ├── notifiers/
│   │   └── telegram.py       # Telegram notifications
│   └── utils/
│       ├── helpers.py        # Helper functions
│       └── logger.py         # Logging setup
└── .github/
    └── workflows/
        └── fly-deploy.yml    # CI/CD workflow
```

---

## 🔧 Logic Chi tiết

### Phát hiện Tích luỹ

**Điều kiện:**
1. ✅ ATR ratio < 0.2% (volatility thấp)
2. ✅ Volume < 70% trung bình (volume giảm)
3. ✅ Price range < 0.8% (sideway)
4. ✅ Bollinger Band width < 1.6%

**Kết quả:**
- Zone: Support - Resistance
- Duration: Thời gian tích luỹ
- Strength: Mạnh/Trung bình

---

### Phát hiện Breakout

**Điều kiện:**
1. ✅ Giá vượt resistance/support + 0.1% buffer
2. ✅ Volume > 1.5x trung bình (xác nhận)
3. ⚠️ Cooldown: 60 phút giữa notifications

**Gợi ý TP/SL:**
```python
# Long setup
SL = min(
    support * 0.995,           # Zone-based
    entry - (ATR * 2)          # ATR-based
)

TP = min(
    entry + zone_width,        # Zone projection
    entry + (risk * 2)         # R:R 1:2
)
```

---

## 📈 Timeframe Strategy

| Timeframe | Style | Risk | SL Range | Hold Time |
|-----------|-------|------|----------|-----------|
| **5m** | ⚡ Scalping | Cao | 0.3-0.8% | < 4h |
| **15m** | 📊 Intraday | Trung bình | 0.5-1.2% | 4-12h |
| **30m** | 📈 Swing ngắn | Trung bình | 0.8-2% | 12-24h |
| **1h** | 🎯 Swing dài | Thấp | 1-3% | 1-3 ngày |

---

## 🔍 Monitoring

### Logs
```bash
# Local
python main.py

# Fly.io
flyctl logs -f
```

### Health Check
```bash
# Local
curl http://localhost:8080/health

# Fly.io
curl https://crypto-trading-assistant.fly.dev/health
```

### Status
```bash
flyctl status
flyctl machine list
```

---

## 💰 Chi phí

### Fly.io
```
VM: 256MB shared-cpu-1x
Region: Singapore
Running: 24/7

Cost: ~$2-3/month
```

### API Calls
```
Binance: Free
Rate limit: 1200 requests/minute
Usage: ~16 requests/minute (4 symbols × 4 timeframes)
```

---

## 🛠️ Development

### Run tests
```bash
pytest tests/
```

### Code quality
```bash
# Format
black .

# Lint
flake8 src/

# Type check
mypy src/
```

---

## 📝 TODO

- [ ] Add backtesting module
- [ ] Support more exchanges (Bybit, OKX)
- [ ] Add persistent zone storage
- [ ] Telegram commands (/status, /zones)
- [ ] Web dashboard
- [ ] Paper trading mode

---

## ⚠️ Disclaimer

**Bot này CHỈ để tham khảo, KHÔNG phải lời khuyên đầu tư.**

- ❌ Không đảm bảo lợi nhuận
- ❌ Crypto có rủi ro cao
- ❌ Tự chịu trách nhiệm về quyết định giao dịch
- ✅ Luôn DYOR (Do Your Own Research)
- ✅ Quản lý rủi ro chặt chẽ
- ✅ Không bao giờ trade với tiền không thể mất

---

## 📄 License

MIT License - Xem [LICENSE](LICENSE) để biết thêm chi tiết.

---

## 🤝 Contributing

Pull requests are welcome! 

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

**⭐ Nếu project hữu ích, hãy cho 1 star nhé!**
```
