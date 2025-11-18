# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

This repository contains **MercariSearcher (MRS)**, an automated Mercari.jp item monitoring system with:
- A **scheduler/worker** that scans Mercari searches on individual intervals and pushes Telegram notifications
- A **Flask web UI** for managing searches and viewing stats/logs
- Optional **Railway deployment** with separate `web` and `worker` processes and PostgreSQL

The architecture is adapted from KufarSearcher (KS1) and split into three main layers:
1. **Runtime entrypoints & processes** (scheduler worker, web UI, WSGI for production)
2. **Core domain logic & infrastructure** (search orchestration, DB, shared state, Telegram worker, proxies, metrics, Railway helpers)
3. **Mercari API layer & scraping** (pyMercariAPI wrapper + HTML scraper as fallback/testing)

Use the commands below as the canonical way to run, test, and deploy the system.

---

## Commands

### Environment & dependencies

From the repo root (`MRS/`):

```bash
# Install Python dependencies (Python 3.11+)
pip install -r requirements.txt

# Copy and edit environment configuration
cp .env.example .env
$EDITOR .env
```

Key env vars (see `configuration_values.py` and `railway_config.py` for details):
- Required: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Common runtime: `DATABASE_URL` (PostgreSQL for Railway, otherwise SQLite file), `SEARCH_INTERVAL`, `MAX_ITEMS_PER_SEARCH`, `PROXY_ENABLED`, `PROXY_LIST`, currency-related vars

### Local runtime

**Worker / scheduler (search + notifications)**

Canonical worker entrypoint is `mercari_notifications.py`:

```bash
# Worker-only mode: run scheduler that executes search cycles and Telegram notifications
python mercari_notifications.py worker
```

Behavior:
- Initializes configuration (`configuration_values.Config`), DB (`db.DatabaseManager`), shared state, `core.MercariSearcher`, proxy/metrics/redeploy helpers
- Schedules periodic jobs (via `schedule`):
  - `search_and_notify` every `config.SEARCH_INTERVAL` seconds
  - daily cleanup (old data)
  - proxy refresh
- Sends a Telegram startup system message listing active searches, then runs an infinite scheduler loop with config hot-reload.

**Web UI (Flask dashboard)**

```bash
# Web UI only (no background worker in this process)
python mercari_notifications.py web

# Access in browser
open "http://localhost:5000"  # or http://<WEB_UI_HOST>:<PORT>
```

Behavior:
- Reuses `MercariNotificationApp` to set up config/DB/shared state
- Starts `web_ui_plugin.app` Flask application on `config.WEB_UI_HOST`/`config.PORT`

**Default mode**

```bash
# Currently equivalent to worker mode
python mercari_notifications.py
```

### Production / Railway

This project is designed to run on Railway with separate `web` and `worker` services (see `Procfile`, `wsgi.py`, and `railway_config.py`).

**Procfile (authoritative process definitions)**

- Web (Flask UI via Gunicorn + WSGI):

  ```bash
  web: gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
  ```

- Worker (search scheduler + Telegram worker):

  ```bash
  worker: python mercari_notifications.py worker
  ```

On Railway, configure at minimum:
- `DATABASE_URL` (Railway PostgreSQL, note the `postgres://` → `postgresql://` fix in `railway_config.get_database_url()`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Optional deployment-related vars (see `railway_config.RAILWAY_SETTINGS` and `configuration_values.Config`):
- `PORT`, `RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`, `MAX_ERRORS_BEFORE_REDEPLOY`, `WEB_CONCURRENCY`, `WORKER_TIMEOUT`, etc.

### Diagnostics, smoke tests, and single-feature tests

These are **module-level test scripts** and diagnostics rather than a formal test suite; use them for quick verification:

From repo root:

```bash
# Validate configuration (env + derived settings)
python configuration_values.py

# Initialize and validate DB (creates tables, prints status)
python db.py

# Exercise Mercari HTML scraper against a sample URL
python mercari_scraper.py   # if it has a __main__ block, or see test below

# Exercise Telegram worker (requires valid TELEGRAM_* env vars)
python simple_telegram_worker.py
```

Mercari-specific tests:

```bash
# Test HTML-based search against a fixed Mercari.jp URL
python test_mercari_search.py

# Test mercapi-based API wrapper search
python test_mercari_api.py
```

These scripts are the closest equivalent to “run a single test” for specific subsystems (DB, config, scraper, API wrapper, Telegram worker).

> There is no dedicated linter/formatter configuration checked into this repo (no `pyproject.toml`, `setup.cfg`, or tool-specific config). Prefer to follow the existing formatting and logging style when editing Python modules.

---

## High-level architecture

### 1. Processes and entrypoints

**Local / dev entrypoint: `mercari_notifications.py`**

- Defines `MercariNotificationApp`, responsible for:
  - Validating configuration (`config.validate_config()`)
  - Initializing DB (`db.get_db()` → `DatabaseManager`)
  - Initializing shared state (`shared_state.get_shared_state()`)
  - Creating `core.MercariSearcher` (core scanning logic)
  - Wiring in:
    - Telegram notification pipeline (`simple_telegram_worker.process_pending_notifications`, `send_system_message`)
    - Proxy management (`proxies.proxy_manager`)
    - Metrics storage (`metrics_storage.metrics_storage`)
    - Auto-redeploy helper (`railway_redeploy.redeployer`)
- Exposes three modes via CLI argument:
  - `worker`: scheduler/worker only (search + Telegram)
  - `web`: Flask UI only
  - default: currently same as `worker` (scheduler)

**Production web entrypoint: `wsgi.py`**

- Sets up logging suitable for Railway (stdout, INFO level)
- Imports `web_ui_plugin.app` as `application` (WSGI callable)
- Used by Gunicorn as configured in `Procfile`.

**Railway process model (`Procfile`)**

- `web`: Gunicorn + `wsgi:application` serves the Flask web UI
- `worker`: `python mercari_notifications.py worker` runs the scheduler + Telegram worker

This split is important for future agents modifying deployment-related code: changes to web-only behavior generally live in `web_ui_plugin.app` / templates, while worker behavior lives in `mercari_notifications.MercariNotificationApp` and `core.MercariSearcher`.

### 2. Core domain & infrastructure

**Configuration (`configuration_values.py`)**

- `Config` class encapsulates all runtime settings, primarily from environment variables:
  - Mercari URLs, DB URLs/paths, Telegram credentials, search interval, rate limits, proxy settings, currency and display preferences
- Supports **hot reload** via `Config.reload_if_needed()`:
  - Periodically pulls configuration overrides from DB (`db.get_all_config()`)
  - Updates key runtime parameters (e.g., `SEARCH_INTERVAL`, `MAX_ITEMS_PER_SEARCH`, proxy and Telegram chat ID) without restart
- `config` is a module-level singleton used across the codebase.

**Database layer (`db.py`)**

- `DatabaseManager` abstracts over **PostgreSQL** (Railway `DATABASE_URL`) and **SQLite** (local file `mercari_scanner.db`):
  - Autodetects backend from `config.DATABASE_URL`, with a Railway-specific fallback to in-memory SQLite if connection fails
  - Creates and migrates core tables on startup:
    - `searches`: search queries + per-query config (URL, filters, scan interval, flags, stats)
    - `items`: scraped items for each search
    - `price_history`: price snapshots per item
    - `settings` / `key_value_store`: config/kv storage powering hot reload
    - `error_tracking`, `logs`: operational telemetry
- Provides higher-level methods used by the rest of the app, e.g.:
  - `get_searches_ready_for_scan()` to locate queries whose `scan_interval` has elapsed
  - `update_search_scan_time`, `update_search_stats`, `increment_api_counter`
  - CRUD and listing for searches/items/logs/stats exposed through the web UI and API.

**Shared runtime state (`shared_state.py`)**

- `SharedState` is an in-process, thread-safe store for ephemeral runtime metrics and flags:
  - Scanner status, total scans, last scan time/duration, items-per-hour
  - DB connectivity flags, proxy state, Telegram state
  - Recent errors and consecutive error counts
- Accessed via module-level helpers (`get_shared_state`, `get_stats_summary`, etc.).
- Web UI uses this to show live status; worker updates it after each scan cycle and notification batch.

**Core scanning logic (`core.py`)**

- `MercariSearcher` orchestrates free-running scans:
  - Constructs a `pyMercariAPI.Mercari` instance (optionally via `proxies.proxy_rotator` if proxies enabled)
  - Provides `search_all_queries()`:
    - Fetches `ready_searches` from DB
    - For each search:
      - Logs metadata
      - Calls `search_query()` to execute Mercari search and persist new items
      - Applies per-request delay based on `config.REQUEST_DELAY_MIN` (and implicitly `REQUEST_DELAY_MAX` inside the API layer)
      - Updates DB stats and next scan time per query
    - Updates shared state and logs an aggregated summary
  - `search_query()` delegates to Mercari API, maps returned items into DB records, and handles proxy rotation on specific errors (e.g., HTTP 403).

**Telegram notifications (`simple_telegram_worker.py`)**

- `TelegramWorker` handles low-level Telegram Bot API requests over HTTP:
  - Uses `config.TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional `TELEGRAM_THREAD_ID`
  - Formats rich HTML messages including JPY and USD prices (using conversion rate and display currency from `config`)
  - Sends photo + caption when possible, with inline keyboard linking back to Mercari item
  - Tracks `total_notifications_sent` and last send time in shared state
  - Implements retry logic and rate-limit handling (HTTP 429 with `retry_after`)
- Higher-level orchestration (`process_pending_notifications`) lives in this module and is invoked from `MercariNotificationApp.search_and_notify()` to flush newly discovered items.

**Proxies, metrics, Railway helpers**

- `proxies.py` (not fully inspected in this pass) is responsible for proxy rotation and health checking, abstracted behind `proxy_manager` and `proxy_rotator` used by searcher and scheduler
- `metrics_storage.py` tracks persisted metrics like last search timestamps, leveraged by the scheduler
- Railway-specific utilities (`railway_config.py`, `railway_redeploy.py`, `check_railway.py`, `setup_railway_*`, etc.) encapsulate:
  - Environment detection (`is_railway_environment`)
  - Normalized DB URL and port discovery
  - Environment validation and optional auto-redeploy behavior when error thresholds are exceeded.

### 3. Mercari integration layer

**pyMercariAPI package (`pyMercariAPI/`)**

- `mercari.py` defines `Mercari`, an adapter around the third-party async `mercapi` library:
  - Provides a **synchronous** interface (`search`, `test_connection`, `change_proxy`) used by `core.MercariSearcher`
  - Handles basic rate limiting between requests
  - Converts `mercapi`’s async search results into internal dicts with Mercari-specific fields (ID, title, price, URLs, optional thumbnails, etc.)
- `items.py` defines `Item` and `Items` domain models around these dicts:
  - Encapsulate useful properties (USD prices, total price including shipping, convenience accessors)
  - Provide simple in-memory filtering/sorting and statistics (count, min/max/avg price, total value).

**HTML scraper (`mercari_scraper.py`)**

- Fallback/experimental scraper for Mercari.jp web pages when API is not used or fails:
  - Uses `requests` + `BeautifulSoup` + regex to extract:
    - Embedded `__INITIAL_STATE__` JSON from Next.js apps
    - Or, as a fallback, item cards from HTML using heuristic selectors
  - Produces the same general item dict structure expected by the rest of the system.
- The CLI test script `test_mercari_search.py` uses `MercariScraper` against a fixed search URL and prints structured results and JSON for inspection.

### 4. Web UI (`web_ui_plugin/`)

- `web_ui_plugin/app.py` is the Flask application used by both local dev and production WSGI:
  - Renders:
    - `/` (dashboard): aggregates DB-level stats (`db.get_statistics()`) and shared-state metrics (`shared_state.get_stats_summary()`), with fallbacks when worker isn’t running
    - `/queries`: manage search definitions from `searches` table
    - `/items`: browse recent items with optional `limit` parameter
    - `/config`: merged view of `Config` defaults plus `settings` overrides
    - `/logs`: paginated, timezone-normalized application logs
  - Exposes REST-style JSON endpoints:
    - `/api/stats`: structured statistics for auto-refresh UI panels
    - `/api/queries`, `/api/queries/add`, plus other query management endpoints
- `wsgi.py` imports this app as `application` for Gunicorn.

The templates and static assets (CSS/JS) live under `web_ui_plugin/templates/` and `web_ui_plugin/static/` and can be adjusted without touching core scanning/notification logic.

---

## How future agents should approach changes

- For **behavioral changes in scanning or notification logic**, focus on:
  - `core.MercariSearcher` (search orchestration and DB/stat updates)
  - `simple_telegram_worker.TelegramWorker` and `process_pending_notifications`
  - DB schema/queries in `db.DatabaseManager` if new data needs to be stored.
- For **new configuration flags or tunables**:
  - Add env var handling to `configuration_values.Config`
  - Wire DB-backed overrides through `db.get_all_config()` and `Config.reload_if_needed()`
  - Surface them on the `/config` page via `web_ui_plugin.app.configuration()`.
- For **web UI changes**, prefer updating:
  - Routes and view logic in `web_ui_plugin/app.py`
  - Jinja templates under `web_ui_plugin/templates/`
  - Static assets under `web_ui_plugin/static/`
- For **deployment concerns** (Railway, process splits, timeouts, DB URLs):
  - Work within `wsgi.py`, `Procfile`, and `railway_config.py` / related Railway helper scripts.
