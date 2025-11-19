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
                             total_api_requests=db.get_api_counter(),
                             config=config)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.log_error(f"Dashboard error: {str(e)}", 'web_ui')
        return f"Error: {e}", 500


@app.route('/queries')
def queries():
    """Search queries management"""
    try:
        searches = db.get_all_searches()
        return render_template('queries.html', searches=searches, config=config)
    except Exception as e:
        logger.error(f"Queries page error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.log_error(f"Queries page error: {str(e)}", 'web_ui')
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
        import traceback
        logger.error(traceback.format_exc())
        db.log_error(f"Items page error: {str(e)}", 'web_ui')
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
    # ВАЖНО: Ключи должны совпадать с именами полей в форме!
    final_config = {
        'SEARCH_INTERVAL': config_dict.get('search_interval', config.SEARCH_INTERVAL),
        'MAX_ITEMS_PER_SEARCH': config_dict.get('max_items_per_search', config.MAX_ITEMS_PER_SEARCH),
        'USD_CONVERSION_RATE': config_dict.get('usd_conversion_rate', config.USD_CONVERSION_RATE),
        'MAX_ERRORS_BEFORE_REDEPLOY': config_dict.get('max_errors_before_redeploy', config.MAX_ERRORS_BEFORE_REDEPLOY),
        'PROXY_ENABLED': config_dict.get('proxy_enabled', config.PROXY_ENABLED),
        'PROXY_LIST': config_dict.get('proxy_list', config.PROXY_LIST),
        'TELEGRAM_BOT_TOKEN': config_dict.get('telegram_bot_token', config.TELEGRAM_BOT_TOKEN),
        'TELEGRAM_CHAT_ID': config_dict.get('telegram_chat_id', config.TELEGRAM_CHAT_ID),
        'RAILWAY_TOKEN': config_dict.get('railway_token', config.RAILWAY_TOKEN),
        # Read-only values from config class
        'APP_NAME': config.APP_NAME,
        'APP_VERSION': config.APP_VERSION,
        'MERCARI_BASE_URL': config.MERCARI_BASE_URL,
        'DISPLAY_CURRENCY': config.DISPLAY_CURRENCY,
        'LOG_LEVEL': config.LOG_LEVEL,
        'PORT': config.PORT,
    }

    return render_template('config.html', config=final_config)


@app.route('/logs')
def logs():
    """Logs page"""
    try:
        import pytz
        from datetime import datetime

        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level', None)
        all_logs = db.get_logs(limit=limit, level=level)

        # Format timestamps to Moscow timezone (GMT+3)
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
        formatted_logs = []
        for log in all_logs:
            log_copy = dict(log)
            if log_copy.get('timestamp'):
                ts = log_copy['timestamp']
                # If timestamp is timezone-aware, convert to Moscow time
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        # Assume it's already Moscow time from database
                        ts = MOSCOW_TZ.localize(ts)
                    else:
                        ts = ts.astimezone(MOSCOW_TZ)
                    # Format as "YYYY-MM-DD HH:MM:SS GMT+3"
                    log_copy['timestamp'] = ts.strftime('%Y-%m-%d %H:%M:%S GMT+3')
                elif isinstance(ts, str):
                    # Already formatted
                    log_copy['timestamp'] = ts
            formatted_logs.append(log_copy)

        return render_template('logs.html', logs=formatted_logs, config=config)
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
        except Exception as e:
            logger.warning(f"Shared state unavailable: {e}")
            uptime_formatted = "N/A (web-only)"

        # Get API request count from database (cross-process visibility)
        total_api_requests = db.get_api_counter()

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

        # Update query with scan settings
        update_data = {
            'search_url': search_url,
            'name': data.get('name'),
            'thread_id': data.get('thread_id'),
            'keyword': data.get('keyword') or validation.get('keyword')
        }
        
        # Add scan_limit and scan_interval if provided
        if 'scan_limit' in data:
            update_data['scan_limit'] = data['scan_limit']
        if 'scan_interval' in data:
            update_data['scan_interval'] = data['scan_interval']
        
        db.update_search(query_id, **update_data)

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
    """Get items API - WITHOUT heavy image_data for fast loading"""
    try:
        limit = request.args.get('limit', 50, type=int)
        all_items = db.get_all_items(limit=limit)
        
        # OPTIMIZATION: Remove heavy image_data from response
        # Frontend will use image_url instead
        for item in all_items:
            if 'image_data' in item:
                del item['image_data']  # Remove 100-500KB base64 data
        
        return jsonify({'success': True, 'items': all_items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recent-items')
def api_get_recent_items():
    """Get recent items for dashboard - WITHOUT heavy image_data"""
    try:
        from datetime import datetime
        import pytz

        # Just get latest 30 items - NO filtering, like items page
        items = db.get_all_items(limit=30)
        
        # OPTIMIZATION: Remove heavy image_data from response
        # This makes API response 10-50x smaller!
        for item in items:
            if 'image_data' in item:
                del item['image_data']  # Remove 100-500KB base64 data
        
        # Moscow timezone (GMT+3)
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')

        return jsonify({
            'success': True,
            'items': items,
            'count': len(items),
            'timestamp': datetime.now(MOSCOW_TZ).isoformat()
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
    """Force scan all queries manually - runs in background to avoid timeout"""
    try:
        logger.info("🔍 Force scan triggered via API")
        db.add_log_entry('INFO', 'Manual scan triggered from web UI', 'api')

        # Run scanner in separate thread to avoid blocking Flask and asyncio conflicts
        import threading
        
        def run_scan():
            try:
                from core import MercariSearcher
                searcher = MercariSearcher()
                results = searcher.search_all_queries()
                
                logger.info(f"✅ Force scan completed: {results}")
                db.add_log_entry('INFO',
                    f"Manual scan completed: {results.get('new_items', 0)} new items found",
                    'api',
                    f"Total: {results.get('total_items_found', 0)}, Searches: {results.get('successful_searches', 0)}")
            except Exception as e:
                logger.error(f"❌ Error in force scan thread: {e}")
                db.add_log_entry('ERROR', f'Manual scan failed: {str(e)}', 'api')
        
        # Start scan in background thread
        scan_thread = threading.Thread(target=run_scan, daemon=True)
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Scan started in background! Check logs for results.'
        })
    except Exception as e:
        logger.error(f"❌ Error starting force scan: {e}")
        db.add_log_entry('ERROR', f'Failed to start manual scan: {str(e)}', 'api')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications/test', methods=['POST'])
def api_test_notification():
    """Send test Telegram notification"""
    try:
        from simple_telegram_worker import send_system_message
        
        # Send test notification (synchronous, no asyncio)
        result = send_system_message("🧪 Test notification from MercariSearcher Web UI")
        
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
        logger.info(f"[CONFIG] /api/config/telegram called with data: {data}")

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
            'message': f'Saved {saved_count} Telegram settings',
            'note': 'Settings will be applied automatically within 10 seconds'
        })
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Error saving telegram config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/proxy', methods=['POST'])
def api_save_proxy_config():
    """Save proxy configuration"""
    try:
        data = request.get_json()
        logger.info(f"[CONFIG] /api/config/proxy called with data: {data}")

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
            'message': f'Saved {saved_count} proxy settings',
            'note': 'Settings will be applied automatically within 10 seconds'
        })
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Error saving proxy config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/railway', methods=['POST'])
def api_save_railway_config():
    """Save Railway configuration"""
    try:
        data = request.get_json()
        logger.info(f"[CONFIG] /api/config/railway called with data: {data}")

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
            'message': f'Saved {saved_count} Railway settings',
            'note': 'Railway token is sensitive and stored securely'
        })
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Error saving railway config: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/railway/status', methods=['GET'])
def api_railway_status():
    """Get Railway auto-redeploy status"""
    try:
        # Get error statistics from database
        recent_errors = db.get_recent_errors(limit=50)
        
        # Count errors by type
        error_counts = {'403': 0, '401': 0, '429': 0, 'other': 0}
        total_errors = 0
        first_error = 'None'
        last_error = 'None'
        
        for error in recent_errors:
            total_errors += 1
            error_msg = error.get('error_message', '')
            
            # Categorize errors
            if '403' in error_msg:
                error_counts['403'] += 1
            elif '401' in error_msg:
                error_counts['401'] += 1
            elif '429' in error_msg:
                error_counts['429'] += 1
            else:
                error_counts['other'] += 1
            
            # Track first and last error times
            if first_error == 'None':
                first_error = str(error.get('occurred_at', 'Unknown'))
            last_error = str(error.get('occurred_at', 'Unknown'))
        
        # Get last redeploy info from config
        last_redeploy = db.load_config('last_railway_redeploy', 'Never')
        
        # Determine status
        max_errors = config.MAX_ERRORS_BEFORE_REDEPLOY
        status = 'active'
        if total_errors >= max_errors:
            status = 'critical'
        elif total_errors >= max_errors // 2:
            status = 'warning'
        
        return jsonify({
            'success': True,
            'status': {
                'status': status,
                'errors': error_counts,
                'total_errors': total_errors,
                'max_errors': max_errors,
                'first_error': first_error,
                'last_error': last_error,
                'last_redeploy': last_redeploy
            }
        })
    except Exception as e:
        logger.error(f"Error getting railway status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/railway/redeploy', methods=['POST'])
def api_railway_redeploy():
    """Trigger Railway redeploy"""
    try:
        import requests
        from datetime import datetime
        
        railway_token = config.RAILWAY_TOKEN
        railway_project_id = config.RAILWAY_PROJECT_ID
        railway_service_id = config.RAILWAY_SERVICE_ID
        
        if not railway_token:
            logger.error("❌ RAILWAY_TOKEN not configured")
            return jsonify({'success': False, 'error': 'Railway token not configured'}), 400
        
        if not railway_project_id or not railway_service_id:
            logger.error("❌ Railway project/service IDs not configured")
            return jsonify({'success': False, 'error': 'Railway project/service IDs not configured'}), 400
        
        logger.info("🔄 Triggering Railway redeploy...")
        
        # Railway GraphQL API endpoint
        url = "https://backboard.railway.app/graphql/v2"
        
        # GraphQL mutation to trigger redeploy
        query = """
        mutation serviceInstanceRedeploy($serviceId: String!) {
            serviceInstanceRedeploy(serviceId: $serviceId)
        }
        """
        
        headers = {
            "Authorization": f"Bearer {railway_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "variables": {
                "serviceId": railway_service_id
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for GraphQL errors
            if 'errors' in result:
                error_msg = result['errors'][0].get('message', 'Unknown error')
                logger.error(f"❌ Railway API error: {error_msg}")
                return jsonify({'success': False, 'error': f'Railway API error: {error_msg}'}), 500
            
            # Save redeploy timestamp
            db.save_config('last_railway_redeploy', datetime.now().isoformat())
            
            logger.info("✅ Railway redeploy triggered successfully")
            db.add_log_entry('INFO', 'Railway redeploy triggered from web UI', 'railway')
            
            return jsonify({
                'success': True,
                'message': 'Railway redeploy triggered successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"❌ Railway API returned status {response.status_code}: {response.text}")
            return jsonify({
                'success': False,
                'error': f'Railway API error: HTTP {response.status_code}'
            }), 500
            
    except requests.exceptions.Timeout:
        logger.error("❌ Railway API request timed out")
        return jsonify({'success': False, 'error': 'Request timed out'}), 500
    except Exception as e:
        logger.error(f"❌ Error triggering redeploy: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/proxy/test', methods=['POST'])
def api_test_proxies():
    """Test proxy connections"""
    try:
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        logger.info("🔍 Testing proxy connections...")
        
        # Get proxy list from config
        proxy_list_str = config.PROXY_LIST
        if isinstance(proxy_list_str, str):
            # Support both newline and comma-separated proxies
            proxy_list = [p.strip() for p in proxy_list_str.replace('\n', ',').split(',') if p.strip()]
        elif isinstance(proxy_list_str, list):
            proxy_list = [p.strip() for p in proxy_list_str if p.strip()]
        else:
            proxy_list = []
        
        if not proxy_list:
            logger.warning("⚠️ No proxies configured to test")
            return jsonify({
                'success': True,
                'total': 0,
                'working': 0,
                'results': [],
                'message': 'No proxies configured'
            })
        
        # Test URL (fast endpoint)
        test_url = "https://jp.mercari.com"
        timeout = 5
        
        def test_proxy(proxy):
            """Test a single proxy"""
            result = {
                'proxy': proxy,
                'working': False,
                'response_time': None,
                'error': None
            }
            
            try:
                start_time = time.time()
                proxies = {
                    'http': proxy,
                    'https': proxy
                }
                
                response = requests.get(test_url, proxies=proxies, timeout=timeout)
                end_time = time.time()
                
                if response.status_code == 200:
                    result['working'] = True
                    result['response_time'] = round((end_time - start_time) * 1000, 2)  # ms
                else:
                    result['error'] = f"HTTP {response.status_code}"
                    
            except requests.exceptions.Timeout:
                result['error'] = "Timeout"
            except requests.exceptions.ProxyError:
                result['error'] = "Proxy connection failed"
            except requests.exceptions.ConnectionError:
                result['error'] = "Connection error"
            except Exception as e:
                result['error'] = str(e)
            
            return result
        
        # Test proxies in parallel
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(test_proxy, proxy): proxy for proxy in proxy_list}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['working']:
                        logger.info(f"✅ Proxy OK: {result['proxy']} ({result['response_time']}ms)")
                    else:
                        logger.warning(f"❌ Proxy FAILED: {result['proxy']} - {result['error']}")
                        
                except Exception as e:
                    logger.error(f"Error testing proxy: {e}")
        
        # Calculate statistics
        working_count = sum(1 for r in results if r['working'])
        total_count = len(results)
        
        logger.info(f"📊 Proxy test completed: {working_count}/{total_count} working")
        db.add_log_entry('INFO', f'Proxy test: {working_count}/{total_count} working', 'proxy')
        
        return jsonify({
            'success': True,
            'total': total_count,
            'working': working_count,
            'results': results,
            'message': f'{working_count} of {total_count} proxies are working'
        })
        
    except Exception as e:
        logger.error(f"❌ Error testing proxies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clear-all-items', methods=['POST'])
def api_clear_all_items():
    """Clear all items from database and trigger new scan"""
    try:
        logger.info("🗑️  Clear all items triggered via API")
        db.add_log_entry('WARNING', 'Clear all items triggered from web UI', 'api')
        
        # Get count before deletion
        stats = db.get_statistics()
        items_count = stats.get('total_items', 0)
        
        # Delete all items
        if db.db_type == 'postgresql':
            db.execute_query("DELETE FROM items")
        else:
            db.execute_query("DELETE FROM items")
        
        logger.info(f"✅ Deleted {items_count} items from database")
        db.add_log_entry('INFO', f'Deleted {items_count} items from database', 'api')
        
        # Trigger new scan in background
        import threading
        
        def run_scan():
            try:
                from core import MercariSearcher
                searcher = MercariSearcher()
                results = searcher.search_all_queries()
                
                logger.info(f"✅ Scan after clear completed: {results}")
                db.add_log_entry('INFO',
                    f"Scan after clear completed: {results.get('new_items', 0)} items found",
                    'api',
                    f"Total: {results.get('total_items_found', 0)}")
            except Exception as e:
                logger.error(f"❌ Error in scan after clear: {e}")
                db.add_log_entry('ERROR', f'Scan after clear failed: {str(e)}', 'api')
        
        scan_thread = threading.Thread(target=run_scan, daemon=True)
        scan_thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {items_count} items. New scan started in background!',
            'deleted_count': items_count
        })
    except Exception as e:
        logger.error(f"❌ Error clearing items: {e}")
        db.add_log_entry('ERROR', f'Failed to clear items: {str(e)}', 'api')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/proxy-image')
def proxy_image():
    """
    Image proxy to bypass Cloudflare hotlink protection
    Returns the image with proper headers so browser can display it
    """
    try:
        import requests
        from flask import Response

        # Get target image URL
        image_url = request.args.get('url')
        if not image_url:
            return "No URL provided", 400

        # Fetch image with proper headers (pretend to be a browser from Mercari)
        # Use Chrome on Mac headers to appear more legitimate
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://jp.mercari.com/',
            'Origin': 'https://jp.mercari.com',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        # Make request with timeout
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)

        if response.status_code == 200:
            # Return image with correct content type
            return Response(
                response.content,
                mimetype=response.headers.get('Content-Type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=86400',  # Cache for 24h
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            logger.warning(f"Failed to fetch image: {response.status_code}")
            return f"Failed to fetch image: {response.status_code}", response.status_code

    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        return f"Error: {str(e)}", 500


@app.route('/api/image/<int:item_id>')
def get_item_image(item_id):
    """
    Serve image from database (base64-encoded)
    This endpoint returns images stored in the database to bypass Cloudflare
    """
    try:
        from flask import Response

        # Query item from database
        query = "SELECT image_data, image_url FROM items WHERE id = %s"
        result = db.execute_query(query, (item_id,), fetch=True)

        if not result or len(result) == 0:
            logger.warning(f"Item {item_id} not found")
            return "Item not found", 404

        item = result[0]
        image_data = item.get('image_data')
        image_url = item.get('image_url')

        # If we have base64 image data, return it
        if image_data:
            # image_data is already a data URI: data:image/jpeg;base64,{data}
            # Extract just the base64 part
            if image_data.startswith('data:'):
                # Parse data URI: data:image/jpeg;base64,{base64data}
                parts = image_data.split(',', 1)
                if len(parts) == 2:
                    content_type = parts[0].split(';')[0].replace('data:', '')
                    base64_data = parts[1]

                    # Decode base64 to bytes
                    import base64
                    image_bytes = base64.b64decode(base64_data)

                    return Response(
                        image_bytes,
                        mimetype=content_type,
                        headers={
                            'Cache-Control': 'public, max-age=2592000',  # Cache for 30 days
                            'Access-Control-Allow-Origin': '*'
                        }
                    )

        # Fallback: if no image_data, redirect to original URL
        if image_url:
            from flask import redirect
            return redirect(image_url)

        # No image at all
        return "No image available", 404

    except Exception as e:
        logger.error(f"Error serving image for item {item_id}: {e}")
        return f"Error: {str(e)}", 500

@app.route('/api/image-proxy')
def image_proxy():
    """Proxy images from Mercari to bypass Cloudflare 403"""
    try:
        image_url = request.args.get('url')
        if not image_url:
            return "No URL provided", 400
        
        # Request image with proper headers to bypass Cloudflare
        import requests
        from flask import Response
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://jp.mercari.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        }
        
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)
        
        if response.status_code == 200:
            return Response(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get('Content-Type', 'image/jpeg'),
                headers={'Cache-Control': 'public, max-age=86400'}
            )
        else:
            logger.error(f"Image proxy failed: {response.status_code} for {image_url}")
            return f"Failed: {response.status_code}", response.status_code
            
    except Exception as e:
        logger.error(f"Image proxy error: {e}")
        return f"Error: {str(e)}", 500


@app.route('/api/proxy/stats')
def api_proxy_stats():
    """Get proxy system statistics and status"""
    try:
        from proxies import proxy_manager, proxy_rotator
        
        if not proxy_manager:
            return jsonify({
                'success': False,
                'error': 'Proxy system disabled',
                'enabled': False
            })
        
        # Get proxy manager stats
        stats = proxy_manager.get_proxy_stats()
        
        # Get current proxy from rotator
        current_proxy = None
        if proxy_rotator and proxy_rotator.current_proxy:
            current_proxy = proxy_rotator.current_proxy
            # Mask credentials for security
            if '@' in current_proxy:
                parts = current_proxy.split('@')
                if len(parts) == 2:
                    # Show only last part (ip:port)
                    current_proxy = f"***@{parts[1]}"
        
        return jsonify({
            'success': True,
            'enabled': True,
            'stats': {
                'total_proxies': stats['total'],
                'working_proxies': stats['working'],
                'failed_proxies': stats['failed'],
                'last_validation': stats['last_validation'],
                'current_proxy': current_proxy,
                'rotation_count': proxy_rotator.request_count if proxy_rotator else 0,
                'rotation_interval': proxy_rotator.rotation_count if proxy_rotator else 0
            }
        })
    except Exception as e:
        logger.error(f"Error getting proxy stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
