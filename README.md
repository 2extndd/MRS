# MRS - Marketplace Research System

Advanced marketplace monitoring and research tool with automated notifications.

## Features

- **Automated Search Monitoring**: Continuously monitors marketplace search results
- **Real-time Notifications**: Telegram alerts for new items
- **Web Dashboard**: Modern UI for managing searches and viewing results
- **Price Tracking**: Monitor price changes and get alerts
- **Multi-Search Support**: Track multiple search queries simultaneously
- **Proxy Support**: Rotate through multiple proxies for reliability
- **Database Storage**: PostgreSQL (production) or SQLite (local development)

## Quick Start

### Requirements

- Python 3.10+
- PostgreSQL (production) or SQLite (development)
- Telegram Bot Token

### Installation

```bash
# Clone repository
git clone https://github.com/2extndd/MRS.git
cd MRS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Configuration

Edit `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
DATABASE_URL=postgresql://...  # or leave empty for SQLite
```

## Usage

### Start Application

```bash
# Start worker (background scanner)
python mercari_notifications.py worker

# Start web UI only
python mercari_notifications.py web

# Start both worker + web UI
python mercari_notifications.py
```

### Web Interface

Access at `http://localhost:8080`

**Pages:**
- **Dashboard**: Overview, statistics, recent items
- **Queries**: Manage search queries
- **Items**: Browse all found items with filtering
- **Config**: System settings
- **Logs**: Application logs and errors

## Adding Search Queries

### Via Web UI

1. Go to **Queries** page
2. Click **Add Query**
3. Enter search URL
4. Configure scan settings
5. Save

### Search URL Format

Paste marketplace search URL with your desired filters:
- Keywords
- Price range (min/max)
- Category
- Item condition
- Size, color, brand
- Shipping options

## Project Structure

```
MRS/
├── mercari_notifications.py    # Main application entry point
├── core.py                      # Core search logic
├── db.py                        # Database manager
├── mercari_scraper.py          # Web scraper
├── configuration_values.py      # Configuration loader
├── shared_state.py             # Cross-process state
├── simple_telegram_worker.py   # Telegram notifications
├── pyMercariAPI/               # API wrapper
│   ├── __init__.py
│   ├── mercari.py              # Main API class
│   ├── items.py                # Item data structures
│   └── exceptions.py           # Custom exceptions
└── web_ui_plugin/              # Web interface
    ├── app.py                  # Flask application
    ├── templates/              # HTML templates
    └── static/                 # CSS, JS, images
```

## Database Schema

**searches**: Search queries
- URL, keyword, filters
- Scan interval, limits
- Active status, statistics

**items**: Found items
- Title, price, currency
- Images, seller info
- Timestamp, sent status

**price_history**: Price tracking
- Item ID, price, timestamp

**logs**: Application logs
- Level, message, timestamp

## Telegram Notifications

Items are sent to Telegram with:
- 📸 Image
- Title and description
- 💰 Price (JPY and USD)
- 🏷️ Brand, condition, size
- 👤 Seller info
- 📍 Location
- 🔗 Direct link

Example:
```
🔔 New Item Found!

Nike Air Max 90
💰 ¥8,500 ($57.12)
🏷️ Brand: Nike | Condition: Like New
📏 Size: 27.5cm
👤 Seller: User123 (4.8⭐)
📍 Tokyo

[View Item]
```

## Configuration Options

### System Settings
- `SEARCH_INTERVAL`: Seconds between scans (default: 300)
- `MAX_ITEMS_PER_SEARCH`: Items to fetch per scan (default: 50)
- `USD_CONVERSION_RATE`: JPY to USD rate (default: 0.0067)

### Proxy Settings
- `PROXY_ENABLED`: Enable/disable proxy rotation
- `PROXY_LIST`: List of proxy URLs

### Railway Auto-Redeploy
- `RAILWAY_TOKEN`: API token for auto-redeploy
- `MAX_ERRORS_BEFORE_REDEPLOY`: Error threshold

## Development

### Local Setup

```bash
# Run with SQLite
python mercari_notifications.py

# Check database
ls -la mercari_scanner.db

# Reset database
rm mercari_scanner.db
```

### Database Migrations

Database tables are created automatically on first run.

## Troubleshooting

### No Items Found

- Check search URL is valid
- Verify filters aren't too restrictive
- Check logs for errors

### Telegram Not Working

- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check `TELEGRAM_CHAT_ID` is valid
- Test with `/api/notifications/test` endpoint

### Proxy Issues

- Test proxies with **Config** → **Test Proxies**
- Remove non-working proxies
- Disable proxy rotation if needed

### Database Errors

```bash
# Check connection
python -c "from db import get_db; db = get_db(); print(db.db_type)"
```

## API Endpoints

### Queries
- `GET /api/queries` - List all queries
- `POST /api/queries/add` - Add new query
- `PUT /api/queries/<id>` - Update query
- `POST /api/queries/<id>/toggle` - Toggle active status
- `POST /api/queries/<id>/delete` - Delete query

### Items
- `GET /api/items` - List items (paginated)
- `GET /api/recent-items` - Recent items for dashboard

### Actions
- `POST /api/force-scan` - Trigger manual scan
- `POST /api/clear-all-items` - Clear all items
- `POST /api/notifications/test` - Test Telegram

## Features Roadmap

- ✅ Web UI with dark theme
- ✅ Infinite scroll pagination
- ✅ Price tracking & alerts
- ✅ Multi-query support
- ✅ Proxy rotation
- ⏳ Advanced filtering in Items page
- ⏳ Export to CSV/JSON
- ⏳ Email notifications

## Credits

Based on [KufarSearcher](https://github.com/2extndd/KS1) architecture.

Developed by [extndd](https://t.me/extndd)

## License

MIT License - see LICENSE file

## Disclaimer

This tool is for personal research and monitoring purposes only. Use responsibly and respect marketplace terms of service.
