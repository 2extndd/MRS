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
        state_stats = shared_state.get_stats_summary()

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
    return render_template('config.html', config=config)


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
    """Get statistics API"""
    try:
        db_stats = db.get_statistics()
        state_stats = shared_state.get_stats_summary()

        return jsonify({
            'success': True,
            'db_stats': db_stats,
            'state_stats': state_stats
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
        search_url = data.get('search_url')

        if not search_url:
            return jsonify({'success': False, 'error': 'search_url required'}), 400

        # Validate URL
        validation = validate_search_url(search_url)
        if not validation.get('valid'):
            return jsonify({'success': False, 'error': validation.get('error', 'Invalid URL')}), 400

        # Add to database
        db.add_search(
            search_url=search_url,
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

        return jsonify({'success': True, 'message': 'Query added successfully'})

    except Exception as e:
        logger.error(f"Error adding query: {e}")
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


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'app': config.APP_NAME, 'version': config.APP_VERSION})


if __name__ == '__main__':
    app.run(host=config.WEB_UI_HOST, port=config.PORT, debug=True)
