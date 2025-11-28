"""
Shared state management for MercariSearcher
Global state storage for runtime variables
Adapted from KufarSearcher
"""

import threading
from datetime import datetime


class SharedState:
    """Thread-safe shared state manager"""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            # Scanner state
            "scanner_running": False,
            "scanner_paused": False,
            "last_scan_time": None,
            "total_scans": 0,
            "active_searches": 0,

            # Application state
            "app_start_time": datetime.now(),
            "worker_status": "stopped",
            "web_ui_status": "stopped",

            # Statistics
            "total_items_found": 0,
            "total_notifications_sent": 0,
            "total_api_requests": 0,
            "total_errors": 0,

            # Performance metrics
            "avg_scan_duration": 0,
            "last_scan_duration": 0,
            "items_per_hour": 0,

            # Error tracking
            "recent_errors": [],
            "last_error_time": None,
            "consecutive_errors": 0,

            # Proxy state
            "proxy_enabled": False,
            "active_proxies": 0,
            "proxy_rotation_count": 0,

            # Database state
            "db_connected": False,
            "db_type": None,  # 'postgresql' or 'sqlite'
            "last_db_error": None,

            # Telegram state
            "telegram_connected": False,
            "last_telegram_send_time": None,
            "telegram_rate_limit_hit": False,

            # Custom flags
            "force_scan_requested": False,
            "shutdown_requested": False,
            
            # Heartbeat
            "last_heartbeat": datetime.now(),
        }

    def update_heartbeat(self):
        """Update last heartbeat timestamp"""
        with self._lock:
            self._state["last_heartbeat"] = datetime.now()

    def get(self, key, default=None):
        """Get state value thread-safely"""
        with self._lock:
            return self._state.get(key, default)

    def set(self, key, value):
        """Set state value thread-safely"""
        with self._lock:
            self._state[key] = value

    def update(self, **kwargs):
        """Update multiple state values"""
        with self._lock:
            self._state.update(kwargs)

    def increment(self, key, amount=1):
        """Increment a numeric state value"""
        with self._lock:
            current = self._state.get(key, 0)
            self._state[key] = current + amount

    def get_all(self):
        """Get entire state dict (copy)"""
        with self._lock:
            return self._state.copy()

    def reset_stats(self):
        """Reset statistics counters"""
        with self._lock:
            self._state.update({
                "total_scans": 0,
                "total_items_found": 0,
                "total_notifications_sent": 0,
                "total_api_requests": 0,
                "total_errors": 0,
                "avg_scan_duration": 0,
                "items_per_hour": 0,
            })

    def add_error(self, error_message):
        """Add error to recent errors list"""
        with self._lock:
            self._state["recent_errors"].append({
                "message": error_message,
                "timestamp": datetime.now()
            })
            # Keep only last 10 errors
            if len(self._state["recent_errors"]) > 10:
                self._state["recent_errors"].pop(0)
            self._state["last_error_time"] = datetime.now()
            self._state["total_errors"] += 1
            self._state["consecutive_errors"] += 1

    def clear_consecutive_errors(self):
        """Reset consecutive error counter"""
        with self._lock:
            self._state["consecutive_errors"] = 0

    def get_uptime(self):
        """Get application uptime in seconds"""
        start_time = self.get("app_start_time")
        if start_time:
            return (datetime.now() - start_time).total_seconds()
        return 0

    def get_uptime_formatted(self):
        """Get formatted uptime string"""
        uptime_seconds = self.get_uptime()
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_scan_stats(self, duration, items_found):
        """Update scanning statistics"""
        # Get uptime outside of lock to avoid deadlock
        uptime_hours = self.get_uptime() / 3600

        with self._lock:
            self._state["last_scan_time"] = datetime.now()
            self._state["last_scan_duration"] = duration
            self._state["total_scans"] += 1
            self._state["total_items_found"] += items_found

            # Calculate average scan duration
            total_scans = self._state["total_scans"]
            current_avg = self._state["avg_scan_duration"]
            new_avg = ((current_avg * (total_scans - 1)) + duration) / total_scans
            self._state["avg_scan_duration"] = new_avg

            # Calculate items per hour
            if uptime_hours > 0:
                self._state["items_per_hour"] = self._state["total_items_found"] / uptime_hours

    def get_stats_summary(self):
        """Get formatted stats summary"""
        # Get uptime outside of lock to avoid deadlock
        uptime_formatted = self.get_uptime_formatted()

        with self._lock:
            return {
                "uptime": uptime_formatted,
                "total_scans": self._state.get("total_scans", 0),
                "total_items_found": self._state.get("total_items_found", 0),
                "total_notifications_sent": self._state.get("total_notifications_sent", 0),
                "total_api_requests": self._state.get("total_api_requests", 0),
                "total_errors": self._state.get("total_errors", 0),
                "avg_scan_duration": round(self._state.get("avg_scan_duration", 0), 2),
                "items_per_hour": round(self._state.get("items_per_hour", 0), 2),
                "scanner_running": self._state.get("scanner_running", False),
                "active_searches": self._state.get("active_searches", 0),
                "proxy_enabled": self._state.get("proxy_enabled", False),
                "active_proxies": self._state.get("active_proxies", 0),
            }


# Global shared state instance
_shared_state = SharedState()


def get_shared_state():
    """Get global shared state instance"""
    return _shared_state


# Convenience functions
def get_state(key, default=None):
    """Get state value"""
    return _shared_state.get(key, default)


def set_state(key, value):
    """Set state value"""
    _shared_state.set(key, value)


def update_state(**kwargs):
    """Update state values"""
    _shared_state.update(**kwargs)


def increment_state(key, amount=1):
    """Increment state value"""
    _shared_state.increment(key, amount)


def get_stats_summary():
    """Get stats summary"""
    return _shared_state.get_stats_summary()


if __name__ == "__main__":
    # Test shared state
    state = get_shared_state()

    print("Testing SharedState...")
    print(f"Initial uptime: {state.get_uptime_formatted()}")

    # Update some stats
    state.set("scanner_running", True)
    state.increment("total_scans", 5)
    state.increment("total_items_found", 15)

    print(f"\nStats summary:")
    for key, value in state.get_stats_summary().items():
        print(f"  {key}: {value}")

    # Test error tracking
    state.add_error("Test error 1")
    state.add_error("Test error 2")
    print(f"\nTotal errors: {state.get('total_errors')}")
    print(f"Consecutive errors: {state.get('consecutive_errors')}")

    state.clear_consecutive_errors()
    print(f"After clearing consecutive: {state.get('consecutive_errors')}")
