# MercariSearcher (MRS)

Automated Mercari.jp item monitoring system with Telegram notifications. Based on [KufarSearcher](https://github.com/2extndd/KS1) architecture.

## Features

- **Automated Search Monitoring**: Continuously monitors Mercari.jp search results
- **Telegram Notifications**: Real-time alerts for new items with photos and details
- **Individual Scan Intervals**: Each search query has its own customizable scan interval (VS5-style)
- **Price Tracking**: Track price changes with historical data and notifications
- **Web Dashboard**: Flask-based UI for managing searches and viewing statistics
- **Railway Deployment**: Ready for cloud deployment on Railway.app
- **Proxy Support**: Built-in proxy rotation for reliable access
- **Currency Conversion**: Displays prices in both JPY and USD

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Telegram Bot (get token from [@BotFather](https://t.me/botfather))
- PostgreSQL database (for production) or SQLite (for local testing)

### 2. Installation

```bash
# Clone repository
git clone <your-repo-url>
cd MRS

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 3. Configuration

Required environment variables in `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Optional but recommended:

```bash
DATABASE_URL=postgresql://...  # For Railway
USD_CONVERSION_RATE=0.0067     # JPY to USD rate
DISPLAY_CURRENCY=USD           # USD or JPY
SEARCH_INTERVAL=300            # Default scan interval (seconds)
```

### 4. Running Locally

```bash
# Run scheduler (worker mode)
python mercari_notifications.py worker

# Or run web UI only
python mercari_notifications.py web

# Or run both (default)
python mercari_notifications.py
```

### 5. Railway Deployment

1. Create new project on [Railway.app](https://railway.app)
2. Add PostgreSQL database
3. Connect GitHub repository
4. Add environment variables in Railway dashboard
5. Deploy!

Railway will automatically:
- Run web UI on `web` service
- Run worker on `worker` service
- Provide PostgreSQL database

## Usage

### Adding Search Queries

#### Via Web UI

1. Open `http://localhost:5000` (or your Railway URL)
2. Go to **Queries** page
3. Click **Add Query**
4. Paste Mercari search URL
5. Set scan interval (default: 300 seconds)

#### Via Mercari.jp

1. Go to [Mercari.jp](https://jp.mercari.com)
2. Search for items with your filters:
   - Keywords: `ナイキ エアマックス` (Nike Air Max)
   - Price range: ¥1,000 - ¥10,000
   - Category, brand, condition, size, etc.
3. Copy the URL from browser
4. Add to MercariSearcher

Example URL:
```
https://jp.mercari.com/search?keyword=ナイキ&price_min=1000&price_max=10000&item_condition_id=1
```

### Search Parameters

Mercari supports these filters:
- `keyword`: Search term (Japanese or English)
- `price_min`, `price_max`: Price range in JPY
- `category_id`: Category ID
- `brand`: Brand name
- `item_condition_id`: Condition (1=New, 2=Like New, 3=Good, etc.)
- `size_id`: Size ID
- `color_id`: Color ID
- `sort`: Sort order (`created_desc`, `price_asc`, `price_desc`)

## Architecture

```
MRS/
├── mercari_notifications.py    # Main application entry point
├── core.py                      # Search logic with individual intervals
├── db.py                        # Database manager (PostgreSQL/SQLite)
├── mercari_scraper.py          # Web scraper for Mercari.jp
├── simple_telegram_worker.py   # Telegram notifications
├── configuration_values.py     # Config management
├── shared_state.py             # Thread-safe state storage
├── proxies.py                  # Proxy rotation
├── railway_*.py                # Railway deployment utilities
├── metrics_storage.py          # Persistent metrics
├── wsgi.py                     # WSGI entry point
├── pyMercariAPI/               # Mercari API wrapper
│   ├── __init__.py
│   ├── mercari.py              # Main API class
│   ├── items.py                # Item data classes
│   └── exceptions.py           # Custom exceptions
├── web_ui_plugin/              # Flask Web UI
│   ├── app.py                  # Flask application
│   ├── templates/              # HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── queries.html
│   │   ├── items.html
│   │   ├── config.html
│   │   └── logs.html
│   └── static/                 # CSS/JS assets
│       ├── css/
│       └── js/
├── requirements.txt            # Python dependencies
├── Procfile                    # Railway process definitions
├── runtime.txt                 # Python version
├── .env.example                # Environment template
└── README.md                   # This file
```

## Database Schema

### Tables

**searches**: Search queries with parameters
- Individual scan intervals per query
- Brand, condition, price range filters
- Price drop notifications flag

**items**: Found items from Mercari
- Mercari ID, title, price (JPY)
- Brand, condition, size, shipping cost
- Seller info, location, images
- Sent status for Telegram notifications

**price_history**: Price tracking
- Item ID, price, timestamp
- For detecting price drops

**settings**: Configuration storage
**error_tracking**: Error monitoring
**logs**: Application logs

## Features Deep Dive

### Individual Scan Intervals

Each search query has its own scan interval, allowing flexible monitoring:
- Popular searches: 60-300 seconds
- Rare items: 600-3600 seconds
- Set per query in Web UI

### Telegram Notifications

Messages include:
- Item photo
- Title and price (JPY + USD)
- Brand, condition, size
- Shipping cost
- Seller info and rating
- Location
- Direct link to Mercari

Format:
```
Nike Air Max 90 - White/Black

💴 Price: $100.50 (¥15,000)
👔 Brand: Nike
✨ Condition: Used - Good
📏 Size: US 10
📦 Shipping: ¥700 ($4.69)
👤 Seller: MercariUser (4.8⭐)
📍 Location: Tokyo

[View on Mercari]
```

### Price Drop Alerts

Enable per search query:
- Tracks price history
- Notifies when price decreases
- Shows previous price

### Web Dashboard

Access at `http://localhost:5000`:
- **Dashboard**: Statistics and system status
- **Queries**: Manage search queries
- **Items**: Browse found items
- **Config**: View configuration
- **Logs**: System logs

### Proxy Support

Enable in `.env`:
```bash
PROXY_ENABLED=true
PROXY_LIST=http://proxy1:8080,http://proxy2:8080,socks5://proxy3:1080
```

Features:
- Automatic rotation
- Health checking
- Failed proxy retry

### Railway Auto-Redeploy

Configure in `.env`:
```bash
RAILWAY_TOKEN=your_token
RAILWAY_PROJECT_ID=your_project_id
RAILWAY_SERVICE_ID=your_service_id
MAX_ERRORS_BEFORE_REDEPLOY=5
```

Automatically redeploys when error threshold is exceeded.

## API Endpoints

### Web UI
- `GET /` - Dashboard
- `GET /queries` - Search queries
- `GET /items` - Items list
- `GET /config` - Configuration
- `GET /logs` - System logs

### REST API
- `GET /api/stats` - Statistics
- `GET /api/queries` - Get all queries
- `POST /api/queries/add` - Add query
- `POST /api/queries/<id>/toggle` - Toggle active
- `POST /api/queries/<id>/delete` - Delete query
- `GET /api/items` - Get items
- `GET /health` - Health check

## Troubleshooting

### Database Connection Issues

Local SQLite:
```bash
# Check database exists
ls -la mercari_scanner.db

# Reset database
rm mercari_scanner.db
python -c "from db import get_db; get_db()"
```

Railway PostgreSQL:
- Check `DATABASE_URL` is set in Railway dashboard
- Verify PostgreSQL service is running

### Telegram Not Working

```bash
# Test bot token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Get chat ID
# Send message to bot, then:
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

### Scraper Errors

- Mercari may have changed HTML structure
- Use proxy if blocked
- Check logs for specific errors

### Railway Deployment

```bash
# View logs
railway logs

# Restart service
railway restart

# Environment variables
railway variables
```

## Development

### Running Tests

```bash
# Test database
python db.py

# Test configuration
python configuration_values.py

# Test scraper
python mercari_scraper.py

# Test Telegram
python simple_telegram_worker.py
```

### Adding Features

1. Fork repository
2. Create feature branch
3. Make changes
4. Test locally
5. Submit pull request

## Performance

- **Scan Speed**: ~2-5 seconds per search
- **Memory**: ~100-200 MB
- **Database**: Grows ~1 MB per 1000 items
- **Notifications**: ~1-2 per second (Telegram limit)

## Limitations

- Mercari.jp only (not Mercari US/UK)
- No official API (uses web scraping)
- Telegram bot required
- Rate limiting: respect Mercari's servers

## Credits

- Based on [KufarSearcher (KS1)](https://github.com/2extndd/KS1) by 2extndd
- Adapted for Mercari.jp marketplace
- Built with Flask, Python-Telegram-Bot, BeautifulSoup

## License

MIT License - see [LICENSE](LICENSE) file

## Support

For issues, questions, or contributions:
- Open GitHub issue
- Check existing issues first
- Provide logs and configuration (remove sensitive data)

## Changelog

### v1.0.0 (2025)
- Initial release
- Mercari.jp support
- Individual scan intervals
- Price tracking
- Web dashboard
- Railway deployment
- Telegram notifications with USD conversion
- Proxy support

---

**Disclaimer**: This tool is for personal use only. Respect Mercari's Terms of Service and robots.txt. Use responsibly with appropriate rate limiting.
