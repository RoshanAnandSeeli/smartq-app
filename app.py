import os
import logging
import requests
import hashlib
from datetime import datetime
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

# ========== LOGGING CONFIGURATION ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("parking_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== CONFIGURATION ==========
TS_READ_KEY   = os.environ.get("THINGSPEAK_READ_KEY",  "<your_read_key>")
TS_CHANNEL_ID = os.environ.get("THINGSPEAK_CHANNEL_ID", "<your_channel_id>")

ANOMALY_THRESHOLD = 20
MAX_VEHICLE_COUNT = 100  # Sanity check: max reasonable vehicle count
MIN_VEHICLE_COUNT = 0
REQUEST_TIMEOUT = 10
CACHE_DURATION = 5  # seconds (ThingSpeak rate limited to 15/min)


def safe_int(value, default=0, min_val=None, max_val=None):
    """
    Convert a value to int safely, returning default on failure.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        min_val: Minimum acceptable value (None to skip)
        max_val: Maximum acceptable value (None to skip)
    
    Returns:
        int: Converted value or default
    """
    try:
        result = int(float(value))
        
        # Validate bounds
        if min_val is not None and result < min_val:
            logger.warning(f"Value {result} below minimum {min_val}, using default {default}")
            return default
        if max_val is not None and result > max_val:
            logger.warning(f"Value {result} exceeds maximum {max_val}, using default {default}")
            return default
            
        return result
    except (TypeError, ValueError):
        logger.debug(f"Failed to convert {value!r} to int, using default {default}")
        return default


def format_timestamp(raw_timestamp):
    """Convert an ISO timestamp into a clean human-readable format."""
    if not raw_timestamp:
        return None
    try:
        dt = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d, %Y %H:%M:%S")
    except Exception:
        return raw_timestamp


class DataValidator:
    """Validates and cleans ThingSpeak data."""
    
    @staticmethod
    def validate_vehicle_count(count):
        """Validate vehicle count is within acceptable range."""
        return safe_int(count, default=0, min_val=MIN_VEHICLE_COUNT, max_val=MAX_VEHICLE_COUNT)
    
    @staticmethod
    def validate_ai_decision(decision):
        """Validate AI decision is 0 or 1."""
        val = safe_int(decision, default=0)
        return 1 if val == 1 else 0
    
    @staticmethod
    def validate_feed(feed):
        """
        Validate and extract required fields from ThingSpeak feed.
        
        Args:
            feed: Feed dict from ThingSpeak
        
        Returns:
            dict: Cleaned feed data or None if invalid
        """
        try:
            if not isinstance(feed, dict):
                logger.warning("Feed is not a dict, skipping")
                return None
            
            vehicle_count = DataValidator.validate_vehicle_count(feed.get("field3"))
            ai_decision = DataValidator.validate_ai_decision(feed.get("field4"))
            
            # Hash the entry_id for blockchain-like security
            entry_id = feed.get("entry_id")
            if entry_id:
                hashed_entry_id = hashlib.sha256(str(entry_id).encode()).hexdigest()
                # Create display version: first 2 chars + ... + last 2 chars
                display_entry_id = f"{hashed_entry_id[:2]}...{hashed_entry_id[-2:]}"
            else:
                hashed_entry_id = None
                display_entry_id = None
            
            return {
                "entry_id":      hashed_entry_id,
                "display_entry_id": display_entry_id,
                "serial_number": entry_id,  # Original ThingSpeak entry ID for display
                "created_at":    format_timestamp(feed.get("created_at")),
                "vehicle_count": vehicle_count,
                "ai_decision":   ai_decision,
                "timestamp":     feed.get("created_at"),
            }
        except Exception as e:
            logger.warning(f"Failed to validate feed: {e}")
            return None


def compute_statistics(vehicle_counts):
    """
    Compute statistics from vehicle counts.
    
    Args:
        vehicle_counts: List of vehicle counts
    
    Returns:
        dict: Statistics including average, min, max, median
    """
    if not vehicle_counts:
        return {
            "average": 0,
            "min": 0,
            "max": 0,
            "median": 0,
            "trend": "stable",
        }
    
    sorted_counts = sorted(vehicle_counts)
    avg = sum(vehicle_counts) / len(vehicle_counts)
    min_val = min(vehicle_counts)
    max_val = max(vehicle_counts)
    
    # Calculate median
    n = len(vehicle_counts)
    median = (sorted_counts[n // 2 - 1] + sorted_counts[n // 2]) / 2 if n % 2 == 0 else sorted_counts[n // 2]
    
    # Simple trend detection (first vs last)
    trend = "increasing" if vehicle_counts[-1] > vehicle_counts[0] else "decreasing" if vehicle_counts[-1] < vehicle_counts[0] else "stable"
    
    return {
        "average": round(avg, 2),
        "min": min_val,
        "max": max_val,
        "median": round(median, 2),
        "trend": trend,
    }


# ========== THINGSPEAK DATA FETCHING ==========
_cache = {"data": None, "timestamp": None}


def get_thingspeak_data(use_cache=True):
    """
    Fetch and validate last 5 entries from ThingSpeak.
    
    Includes:
    - Data validation and cleaning
    - Anomaly detection
    - Statistical analysis
    - Robust error handling
    - Optional caching
    
    Args:
        use_cache: Whether to use cached data if recent
    
    Returns:
        dict: Structured response with status, counts, statistics, and error info
    """
    try:
        # Check cache
        if use_cache and _cache["data"] and _cache["timestamp"]:
            age = (datetime.now() - _cache["timestamp"]).total_seconds()
            if age < CACHE_DURATION:
                logger.debug(f"Returning cached data (age: {age:.1f}s)")
                return _cache["data"]
        
        logger.info("Fetching ThingSpeak data...")
        url = f"https://api.thingspeak.com/channels/{TS_CHANNEL_ID}/feeds.json"
        response = requests.get(
            url,
            params={"api_key": TS_READ_KEY, "results": 5},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        feeds = response.json().get("feeds", [])
        
        if not feeds:
            logger.warning("No feeds returned from ThingSpeak")
            raise ValueError("No feeds returned from ThingSpeak.")
        
        logger.info(f"Received {len(feeds)} feeds from ThingSpeak")
        
        # Validate and clean all feeds
        validator = DataValidator()
        history = []
        for feed in feeds:
            cleaned = validator.validate_feed(feed)
            if cleaned:
                history.append(cleaned)
        
        if not history:
            logger.error("No valid feeds after validation")
            raise ValueError("No valid feeds after data validation.")
        
        logger.info(f"Validated {len(history)} feeds")
        
        # Extract vehicle counts and AI decisions
        vehicle_counts = [h["vehicle_count"] for h in history]
        ai_decisions = [h["ai_decision"] for h in history]
        
        # Compute current state
        latest_vehicle_count = vehicle_counts[-1]
        latest_ai_decision = ai_decisions[-1]
        latest_status = "BUSY" if latest_ai_decision == 1 else "FREE"
        
        # Compute statistics
        stats = compute_statistics(vehicle_counts)
        
        # Anomaly detection
        anomaly = latest_vehicle_count > ANOMALY_THRESHOLD
        if anomaly:
            logger.warning(f"ANOMALY DETECTED: Vehicle count {latest_vehicle_count} > threshold {ANOMALY_THRESHOLD}")
        
        # Build response
        result = {
            "timestamp": datetime.now().astimezone().strftime("%b %d, %Y %H:%M:%S"),
            "vehicle_count": latest_vehicle_count,
            "status": latest_status,
            "statistics": stats,
            "anomaly": anomaly,
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "history": history,
            "error": None,
        }
        
        # Update cache
        _cache["data"] = result
        _cache["timestamp"] = datetime.now()
        
        logger.info(f"Success: {latest_vehicle_count} vehicles, status={latest_status}, anomaly={anomaly}")
        return result
        
    except requests.exceptions.Timeout:
        msg = f"ThingSpeak request timed out (timeout={REQUEST_TIMEOUT}s)"
        logger.error(msg)
        return _error_response(msg, "TIMEOUT")
    except requests.exceptions.ConnectionError as e:
        msg = f"Connection error to ThingSpeak: {e}"
        logger.error(msg)
        return _error_response(msg, "CONNECTION_ERROR")
    except requests.exceptions.HTTPError as e:
        msg = f"HTTP error from ThingSpeak: {e.response.status_code} - {e}"
        logger.error(msg)
        return _error_response(msg, "HTTP_ERROR")
    except requests.exceptions.RequestException as e:
        msg = f"ThingSpeak request failed: {e}"
        logger.error(msg)
        return _error_response(msg, "REQUEST_ERROR")
    except ValueError as e:
        msg = str(e)
        logger.error(msg)
        return _error_response(msg, "VALIDATION_ERROR")
    except Exception as e:
        msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.exception(msg)
        return _error_response(msg, "UNEXPECTED_ERROR")


def _error_response(message, error_code=None):
    """
    Return a safe default response dict with error information.
    
    Args:
        message: Error message
        error_code: Error category (e.g., TIMEOUT, VALIDATION_ERROR)
    
    Returns:
        dict: Error response structure
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "vehicle_count": None,
        "status": None,
        "statistics": {
            "average": None,
            "min": None,
            "max": None,
            "median": None,
            "trend": None,
        },
        "anomaly": False,
        "anomaly_threshold": ANOMALY_THRESHOLD,
        "history": [],
        "error": message,
        "error_code": error_code,
    }



# ========== API ROUTES ==========

@app.route("/", methods=["GET"])
def dashboard():
    """
    Render the Smart Parking Dashboard.
    
    Returns:
        HTML: Dashboard page with real-time parking data
    """
    logger.info("GET / endpoint called (dashboard)")
    try:
        data = get_thingspeak_data()
        return render_template("index.html", data=data)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return render_template("index.html", data={
            "error": "Unable to load dashboard",
            "vehicle_count": None,
            "status": None,
            "statistics": {},
            "anomaly": False,
            "history": [],
        }), 500


@app.route("/status", methods=["GET"])
def status():
    """
    Get current parking system status.
    
    Returns:
        JSON: {
            "timestamp": ISO 8601 timestamp,
            "vehicle_count": Current number of vehicles,
            "status": "BUSY" or "FREE",
            "statistics": {
                "average": Average count in last 5 entries,
                "min": Minimum count,
                "max": Maximum count,
                "median": Median count,
                "trend": "increasing", "decreasing", or "stable"
            },
            "anomaly": Boolean indicating if anomaly detected,
            "anomaly_threshold": Threshold value,
            "history": Array of last 5 entries,
            "error": Error message (null if successful),
            "error_code": Error category (null if successful)
        }
    """
    logger.info("GET /status endpoint called")
    data = get_thingspeak_data()
    code = 200 if data["error"] is None else 502
    return jsonify(data), code


@app.route("/status/detailed", methods=["GET"])
def status_detailed():
    """
    Get detailed parking system status with analysis.
    Same as /status but with additional analysis hints.
    
    Returns:
        JSON: Same as /status with added analysis
    """
    logger.info("GET /status/detailed endpoint called")
    data = get_thingspeak_data()
    
    if data["error"] is None:
        # Add analysis
        stats = data["statistics"]
        vehicle_count = data["vehicle_count"]
        
        analysis = {
            "is_full": vehicle_count > stats["average"] * 1.5,
            "occupancy_level": round((vehicle_count / 100) * 100, 1),  # percentage if max is 100
            "capacity_warning": data["anomaly"],
            "trend_direction": stats["trend"],
        }
        data["analysis"] = analysis
    
    code = 200 if data["error"] is None else 502
    return jsonify(data), code


@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint.
    
    Returns:
        JSON: {"ok": true} with 200 status
    """
    logger.debug("GET /health endpoint called")
    return jsonify({"ok": True, "timestamp": datetime.now().isoformat()}), 200


@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    """
    Clear the internal data cache (debugging endpoint).
    
    Returns:
        JSON: {"cleared": true}
    """
    global _cache
    _cache = {"data": None, "timestamp": None}
    logger.info("Cache cleared via API")
    return jsonify({"cleared": True, "timestamp": datetime.now().isoformat()}), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    logger.warning(f"404 Not Found: {error}")
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"500 Internal Error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ========== APPLICATION ENTRY POINT ==========

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Smart Parking System Flask Backend Starting")
    logger.info("=" * 50)
    logger.info(f"ThingSpeak Channel: {TS_CHANNEL_ID}")
    logger.info(f"Anomaly Threshold: {ANOMALY_THRESHOLD} vehicles")
    logger.info(f"Max Safe Count: {MAX_VEHICLE_COUNT} vehicles")
    logger.info(f"Cache Duration: {CACHE_DURATION}s")
    logger.info("=" * 50)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
