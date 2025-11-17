"""
Flask Web UI for MercariSearcher
Adapted from KufarSearcher
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import logging
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import get_db
from configuration_values import config
from shared_state import get_shared_state
from core import validate_search_url

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Database and state
db = get_db()
shared_state = get_shared_state()


@app.route('/')
def index():
    """Dashboard"""
    try:
        stats = db.get_statistics()
        # Try to get shared_state stats with timeout fallback
        try:
            state_stats = shared_state.get_stats_summary()
        except Exception as e:
            logger.warning(f"Shared state unavailable (web-only mode?): {e}")
            # Provide default stats for web-only mode
            state_stats = {
                "scanner_running": False,
                "scanner_paused": False,
                "uptime": "N/A (web-only mode)",
                "total_scans": 0,
                "total_items_found": 0,
                "items_per_hour": 0,
                "avg_scan_duration": 0,
                "worker_status": "not running",
                "telegram_connected": False
            }

        return render_template('dashboard.html',
                             stats=stats,
                             state_stats=state_stats,
                             config=config)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Error: {e}", 500


@app.route('/queries')
def queries():
    """Search queries management"""
    try:
        searches = db.get_all_searches()
        return render_template('queries.html', searches=searches, config=config)
    except Exception as e:
        logger.error(f"Queries page error: {e}")
        return f"Error: {e}", 500


@app.route('/items')
def items():
    """Items list"""
    try:
        limit = request.args.get('limit', 100, type=int)
        all_items = db.get_all_items(limit=limit)
        return render_template('items.html', items=all_items, config=config)
    except Exception as e:
        logger.error(f"Items page error: {e}")
        return f"Error: {e}", 500


@app.route('/config')
def configuration():
    """Configuration page"""
    # Load config from database
    config_dict = {}
    try:
        all_config = db.get_all_config()
        for key, value in all_config.items():
            # Remove 'config_' prefix if present
            clean_key = key.replace('config_', '')
            # Try to convert to appropriate type
            try:
                # Try int first
                config_dict[clean_key] = int(value)
            except (ValueError, TypeError):
                # Try bool
                if isinstance(value, str) and value.lower() in ('true', 'false'):
                    config_dict[clean_key] = value.lower() == 'true'
                else:
                    # Keep as string
                    config_dict[clean_key] = value
    except Exception as e:
        logger.error(f"Error loading config from database: {e}")

    # Create final config dict from Config class attributes + DB overrides
    final_config = {
        'SEARCH_INTERVAL': config_dict.get('scan_interval', config.SEARCH_INTERVAL),
        'MAX_ITEMS_PER_SEARCH': config_dict.get('max_items', config.MAX_ITEMS_PER_SEARCH),
        'REQUEST_DELAY_MIN': config_dict.get('request_delay', config.REQUEST_DELAY_MIN),
        'PROXY_ENABLED': config_dict.get('proxy_enabled', config.PROXY_ENABLED),
        'TELEGRAM_BOT_TOKEN': config.TELEGRAM_BOT_TOKEN,
        'TELEGRAM_CHAT_ID': config.TELEGRAM_CHAT_ID,
    }

    return render_template('config.html', config=final_config)


@app.route('/logs')
def logs():
    """Logs page"""
    try:
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level', None)
        all_logs = db.get_logs(limit=limit, level=level)
        return render_template('logs.html', logs=all_logs, config=config)
    except Exception as e:
        logger.error(f"Logs page error: {e}")
        return f"Error: {e}", 500


# ==================== API ROUTES ====================

@app.route('/api/stats')
def api_stats():
    """Get statistics API - formatted for auto-refresh"""
    try:
        import datetime as dt

        db_stats = db.get_statistics()

        # Try to get shared state stats
        try:
            state_stats = shared_state.get_stats_summary()
            uptime_formatted = state_stats.get('uptime', 'N/A')
            total_api_requests = state_stats.get('total_api_requests', 0)
        except Exception as e:
            logger.warning(f"Shared state unavailable: {e}")
            uptime_formatted = "N/A (web-only)"
            total_api_requests = 0

        return jsonify({
            'success': True,
            'database': {
                'total_items': db_stats.get('total_items', 0),
                'active_searches': db_stats.get('active_searches', 0),
                'unsent_items': db_stats.get('unsent_items', 0)
            },
            'total_api_requests': total_api_requests,
            'uptime_formatted': uptime_formatted,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries', methods=['GET'])
def api_get_queries():
    """Get all queries"""
    try:
        searches = db.get_all_searches()
        return jsonify({'success': True, 'queries': searches})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/add', methods=['POST'])
def api_add_query():
    """Add new query"""
    try:
        data = request.get_json()
        logger.info(f"[API] /api/queries/add called with data: {data}")

        search_url = data.get('search_url')

        if not search_url:
            logger.error("[API] No search_url provided!")
            return jsonify({'success': False, 'error': 'search_url required'}), 400

        # Validate URL
        logger.info(f"[API] Validating URL: {search_url}")
        validation = validate_search_url(search_url)
        if not validation.get('valid'):
            logger.error(f"[API] URL validation failed: {validation.get('error')}")
            return jsonify({'success': False, 'error': validation.get('error', 'Invalid URL')}), 400

        # Add to database
        logger.info(f"[API] Adding search to database: {data.get('name')}")
        search_id = db.add_search(
            search_url=search_url,
            name=data.get('name'),
            thread_id=data.get('thread_id'),
            keyword=data.get('keyword') or validation.get('keyword'),
            min_price=data.get('min_price') or validation.get('min_price'),
            max_price=data.get('max_price') or validation.get('max_price'),
            category_id=data.get('category_id') or validation.get('category_id'),
            brand=data.get('brand') or validation.get('brand'),
            condition=data.get('condition') or validation.get('condition'),
            size=data.get('size') or validation.get('size'),
            scan_interval=data.get('scan_interval', 300),
            notify_on_price_drop=data.get('notify_on_price_drop', False)
        )

        logger.info(f"[API] ✅ Query added successfully! ID: {search_id}")
        return jsonify({'success': True, 'message': 'Query added successfully', 'id': search_id})

    except Exception as e:
        logger.error(f"[API] ❌ Error adding query: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/<int:query_id>', methods=['GET'])
def api_get_query(query_id):
    """Get single query details"""
    try:
        query = db.get_search_by_id(query_id)
        if not query:
            return jsonify({'success': False, 'error': 'Query not found'}), 404
        return jsonify({'success': True, 'query': query})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/<int:query_id>', methods=['PUT'])
def api_update_query(query_id):
    """Update query"""
    try:
        data = request.get_json()
        search_url = data.get('search_url')

        if not search_url:
            return jsonify({'success': False, 'error': 'search_url required'}), 400

        # Validate URL
        validation = validate_search_url(search_url)
        if not validation.get('valid'):
            return jsonify({'success': False, 'error': validation.get('error', 'Invalid URL')}), 400

        # Update query
        db.update_search(
            query_id,
            search_url=search_url,
            name=data.get('name'),
            thread_id=data.get('thread_id'),
            keyword=data.get('keyword') or validation.get('keyword')
        )

        return jsonify({'success': True, 'message': 'Query updated successfully'})

    except Exception as e:
        logger.error(f"Error updating query: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/<int:query_id>/toggle', methods=['POST'])
def api_toggle_query(query_id):
    """Toggle query active status"""
    try:
        new_status = db.toggle_search_active(query_id)
        return jsonify({'success': True, 'is_active': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/queries/<int:query_id>/delete', methods=['POST'])
def api_delete_query(query_id):
    """Delete query"""
    try:
        db.delete_search(query_id)
        return jsonify({'success': True, 'message': 'Query deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/items')
def api_get_items():
    """Get items API"""
    try:
        limit = request.args.get('limit', 50, type=int)
        all_items = db.get_all_items(limit=limit)
        return jsonify({'success': True, 'items': all_items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recent-items')
def api_get_recent_items():
    """Get recent items (last 24 hours) for dashboard auto-refresh"""
    try:
        import json
        from datetime import datetime, timedelta

        # Get items from last 24 hours
        recent_items = []
        all_items = db.get_all_items(limit=100)

        cutoff_time = datetime.now() - timedelta(hours=24)

        for item in all_items:
            try:
                # Parse found_at timestamp
                if isinstance(item.get('found_at'), str):
                    # Try parsing RFC 2822 format (e.g., "Mon, 17 Nov 2025 16:21:17 GMT")
                    from email.utils import parsedate_to_datetime
                    try:
                        item_time = parsedate_to_datetime(item['found_at'])
                    except:
                        # Fallback to ISO format
                        item_time = datetime.fromisoformat(item['found_at'].replace('Z', '+00:00'))

                    if item_time.replace(tzinfo=None) >= cutoff_time:
                        # Parse JSON fields if needed
                        if isinstance(item.get('images'), str):
                            try:
                                item['images'] = json.loads(item['images'])
                            except:
                                item['images'] = []

                        # Get first image URL
                        item['image_url'] = item['images'][0] if item.get('images') else None

                        recent_items.append(item)
            except Exception as e:
                logger.warning(f"Error parsing item timestamp: {e}")
                continue

        # Limit to 30 most recent
        recent_items = recent_items[:30]

        return jsonify({
            'success': True,
            'items': recent_items,
            'count': len(recent_items),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting recent items: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search/test', methods=['POST'])
def api_test_search():
    """Test search URL validity"""
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({'valid': False, 'error': 'URL is required'}), 400

        # Validate URL
        result = validate_search_url(url)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing search URL: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/force-scan', methods=['POST'])
def api_force_scan():
    """Force scan all queries manually"""
    try:
        logger.info("🔍 Force scan triggered via API")
        db.add_log_entry('INFO', 'Manual scan triggered from web UI', 'api')

        # Import and run scanner
        from core import MercariSearcher
        searcher = MercariSearcher()
        results = searcher.search_all_queries()

        logger.info(f"✅ Force scan completed: {results}")
        db.add_log_entry('INFO',
            f"Manual scan completed: {results.get('new_items', 0)} new items found",
            'api',
            f"Total: {results.get('total_items_found', 0)}, Searches: {results.get('successful_searches', 0)}")

        return jsonify({
            'success': True,
            'new_items': results.get('new_items', 0),
            'total_items': results.get('total_items_found', 0),
            'message': f'Scan completed! Found {results.get("new_items", 0)} new items.'
        })
    except Exception as e:
        logger.error(f"❌ Error in force scan: {e}")
        db.add_log_entry('ERROR', f'Manual scan failed: {str(e)}', 'api')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications/test', methods=['POST'])
def api_test_notification():
    """Send test Telegram notification"""
    try:
        import asyncio
        from simple_telegram_worker import send_test_notification

        # Send test notification
        result = asyncio.run(send_test_notification())

        if result:
            return jsonify({'success': True, 'message': 'Test notification sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send test notification'}), 500
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'app': config.APP_NAME, 'version': config.APP_VERSION})


if __name__ == '__main__':
    app.run(host=config.WEB_UI_HOST, port=config.PORT, debug=True)


# ==================== CONFIG API ENDPOINTS ====================

@app.route('/api/config/system', methods=['POST'])
def api_save_system_config():
    """Save system configuration"""
    try:
        data = request.get_json()
        logger.info(f"[CONFIG] /api/config/system called with data: {data}")

        # Save each config value to database
        saved_count = 0
        for key, value in data.items():
            logger.info(f"[CONFIG] Saving config_{key} = {value}")
            if db.save_config(f"config_{key}", value):
                saved_count += 1
                logger.info(f"[CONFIG] ✅ Saved config_{key}")
            else:
                logger.error(f"[CONFIG] ❌ Failed to save config_{key}")

        logger.info(f"[CONFIG] Total saved: {saved_count}/{len(data)}")

        return jsonify({
            'success': True,
            'message': f'Saved {saved_count} settings to database',
            'note': 'Settings will be applied automatically within 10 seconds'
        })
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Error saving system config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/telegram', methods=['POST'])
def api_save_telegram_config():
    """Save Telegram configuration"""
    try:
        data = request.get_json()
        # TODO: Implement config saving
        logger.info(f"Telegram config update requested: {data}")
        return jsonify({'success': True, 'message': 'Telegram settings saved'})
    except Exception as e:
        logger.error(f"Error saving telegram config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/proxy', methods=['POST'])
def api_save_proxy_config():
    """Save proxy configuration"""
    try:
        data = request.get_json()
        # TODO: Implement config saving
        logger.info(f"Proxy config update requested: {data}")
        return jsonify({'success': True, 'message': 'Proxy settings saved'})
    except Exception as e:
        logger.error(f"Error saving proxy config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/railway', methods=['POST'])
def api_save_railway_config():
    """Save Railway configuration"""
    try:
        data = request.get_json()
        # TODO: Implement config saving
        logger.info(f"Railway config update requested: {data}")
        return jsonify({'success': True, 'message': 'Railway settings saved'})
    except Exception as e:
        logger.error(f"Error saving railway config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/railway/status', methods=['GET'])
def api_railway_status():
    """Get Railway auto-redeploy status"""
    try:
        # TODO: Implement actual error tracking
        return jsonify({
            'success': True,
            'status': {
                'status': 'active',
                'errors': {'403': 0, '401': 0, '429': 0},
                'total_errors': 0,
                'first_error': 'None',
                'last_error': 'None',
                'last_redeploy': 'Never'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/railway/redeploy', methods=['POST'])
def api_railway_redeploy():
    """Trigger Railway redeploy"""
    try:
        # TODO: Implement Railway API integration
        logger.warning("⚠️ Railway redeploy requested (not implemented yet)")
        return jsonify({'success': False, 'error': 'Redeploy not implemented yet'}), 501
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/proxy/test', methods=['POST'])
def api_test_proxies():
    """Test proxy connections"""
    try:
        # TODO: Implement proxy testing
        logger.info("Proxy test requested")
        return jsonify({'success': True, 'total': 0, 'working': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
