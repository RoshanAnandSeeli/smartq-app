# Smart Parking System - Backend Design Guide

## 📋 Overview

This document describes the improved Flask backend for the IoT Smart Parking System. The system fetches vehicle data from ThingSpeak, processes it through an AI engine (Groq LLM), and provides real-time parking status via REST API.

## 🏗️ Architecture

```
Arduino (HC-SR04 Sensor)
        ↓
   ThingSpeak Cloud
     ↙          ↖
Flask Backend   Smart AI (smart_parking_ai.py)
        ↓
   Dashboard/Frontend
```

## 📊 ThingSpeak Field Mapping

| Field | Purpose | Range | Description |
|-------|---------|-------|-------------|
| field1 | Vehicle Detection | 0/1 | Raw sensor trigger |
| field2 | Payment/Access | 0/1 | Access control status |
| field3 | Vehicle Count | 0-100 | Current parking lot occupancy |
| field4 | AI Decision | 0/1 | 0=Free, 1=Busy (from smart_parking_ai.py) |

## 🔧 Backend Features

### 1. **Data Validation & Cleaning**
- Safe integer conversion with fallback defaults
- Bounds checking (0-100 vehicles)
- NaN/None value handling
- Feed integrity validation

### 2. **Statistical Analysis**
- **Average**: Mean of last 5 vehicle counts
- **Median**: Middle value for outlier resistance
- **Min/Max**: Range of values
- **Trend**: Increasing/Decreasing/Stable detection

### 3. **Anomaly Detection**
- Automatic flagging when vehicle count > 20
- Prevents system overload conditions
- Includes threshold in response

### 4. **Smart Caching**
- 5-second cache to respect ThingSpeak rate limits (15 req/min)
- Automatic cache expiration
- Cache bypass option available

### 5. **Robust Error Handling**
- Timeout handling (10s default)
- Connection error recovery
- HTTP error distinction
- Structured error responses with error codes

### 6. **Logging & Monitoring**
- Dual output: Console + File (`parking_system.log`)
- Debug logging for development
- Error tracking for troubleshooting
- Performance metrics (cache hits, API times)

## 📡 API Endpoints

### 1. **GET /status**
Returns current parking status and statistics.

**Response (Success):**
```json
{
  "timestamp": "2026-04-09T10:30:45.123456",
  "vehicle_count": 15,
  "status": "FREE",
  "statistics": {
    "average": 12.4,
    "min": 10,
    "max": 18,
    "median": 12.0,
    "trend": "increasing"
  },
  "anomaly": false,
  "anomaly_threshold": 20,
  "history": [
    {
      "entry_id": 12345,
      "created_at": "2026-04-09T10:30:30Z",
      "vehicle_count": 10,
      "ai_decision": 0,
      "timestamp": "2026-04-09T10:30:30+00:00"
    },
    ...
  ],
  "error": null,
  "error_code": null
}
```

**Response (Error):**
```json
{
  "timestamp": "2026-04-09T10:30:45.123456",
  "vehicle_count": null,
  "status": null,
  "statistics": {
    "average": null,
    "min": null,
    "max": null,
    "median": null,
    "trend": null
  },
  "anomaly": false,
  "anomaly_threshold": 20,
  "history": [],
  "error": "ThingSpeak request timed out (timeout=10s)",
  "error_code": "TIMEOUT"
}
```

**Status Codes:**
- `200`: Success (populated data)
- `502`: API failure (error provided in response)

### 2. **GET /status/detailed**
Same as `/status` with additional analysis.

**Additional Fields:**
```json
{
  "analysis": {
    "is_full": false,
    "occupancy_level": 15.0,
    "capacity_warning": false,
    "trend_direction": "increasing"
  }
}
```

### 3. **GET /health**
Simple health check endpoint.

**Response:**
```json
{
  "ok": true,
  "timestamp": "2026-04-09T10:30:45.123456"
}
```

### 4. **POST /cache/clear**
Clears internal cache (useful for testing/debugging).

**Response:**
```json
{
  "cleared": true,
  "timestamp": "2026-04-09T10:30:45.123456"
}
```

## 🛡️ Error Handling

The system handles various error scenarios gracefully:

| Error Type | Cause | HTTP Code | Error Code |
|------------|-------|-----------|------------|
| Timeout | API takes > 10s | 502 | TIMEOUT |
| Connection Error | Network issues | 502 | CONNECTION_ERROR |
| HTTP Error | 4xx/5xx from ThingSpeak | 502 | HTTP_ERROR |
| Validation Error | Invalid/missing data | 502 | VALIDATION_ERROR |
| Unexpected Error | Unknown exception | 502 | UNEXPECTED_ERROR |

**Key Point:** System **never crashes**. Always returns valid JSON with error information.

## ⚙️ Configuration

Edit these values in `app.py` for your requirements:

```python
ANOMALY_THRESHOLD = 20        # Vehicles (trigger anomaly if exceeded)
MAX_VEHICLE_COUNT = 100       # Sanity check max value
MIN_VEHICLE_COUNT = 0         # Sanity check min value
REQUEST_TIMEOUT = 10          # Seconds for ThingSpeak API
CACHE_DURATION = 5            # Seconds (respects 15 req/min limit)
```

## 🚀 Setup & Deployment

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Configure Environment**
Create `.env` file with your credentials:
```
THINGSPEAK_CHANNEL_ID=<your_channel_id>
THINGSPEAK_READ_KEY=<your_read_key>
THINGSPEAK_WRITE_KEY=<your_write_key>
GROQ_API_KEY=<your_groq_api_key>
```

### 3. **Run Backend**
```bash
python app.py
```
Server starts at `http://localhost:5000`

### 4. **Monitor Logs**
```bash
tail -f parking_system.log
```

### 5. **Production Deployment** (Optional)
Use Gunicorn instead of Flask development server:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📊 Data Quality Assurance

### Validation Pipeline:
1. ✅ Fetch from ThingSpeak
2. ✅ Check response structure
3. ✅ Parse individual feeds
4. ✅ Validate field3 (vehicle count): 0-100
5. ✅ Validate field4 (AI decision): 0 or 1
6. ✅ Compute statistics
7. ✅ Detect anomalies
8. ✅ Cache result

### Automatic Recovery:
- Missing fields → Defaults to 0
- Invalid types → Safely converted to int
- Out-of-range values → Bounded to acceptable range
- Invalid feeds → Skipped, others processed

## 🔍 Debugging

### Enable Debug Logging:
Edit line 15 in `app.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # More verbose output
```

### Clear Cache Manually:
```bash
curl -X POST http://localhost:5000/cache/clear
```

### Test Endpoints:
```bash
# Get status
curl http://localhost:5000/status

# Get detailed status
curl http://localhost:5000/status/detailed

# Health check
curl http://localhost:5000/health
```

## 📈 Integration with Smart Parking AI

The main AI loop (`smart_parking_ai.py`) runs independently:
1. Fetches vehicle counts via `get_data()` from field3
2. Sends to Groq LLM with retry logic
3. Receives AI decision (Busy/Free)
4. Writes to field4 in ThingSpeak
5. Flask backend reads field4 via `/status` endpoint

### Flow:
```
smart_parking_ai.py                Flask Backend
    ↓                                  ↓
Fetch field3 (counts)          Read field3 & field4
    ↓                                  ↓
Send to Groq LLM              Compute statistics
    ↓                                  ↓
Get decision (0/1)            Detect anomalies
    ↓                                  ↓
Write to field4                Return structured JSON
```

## 🎯 Key Improvements Made

1. ✅ **DataValidator class** - Comprehensive data validation
2. ✅ **compute_statistics()** - Advanced metrics (median, trend, min/max)
3. ✅ **Proper logging** - File + console output
4. ✅ **Smart caching** - Respects API rate limits
5. ✅ **Error codes** - Specific error categorization
6. ✅ **Timestamps** - Every response timestamped
7. ✅ **Detailed API docs** - Added docstrings to all endpoints
8. ✅ **Additional endpoints** - /status/detailed, /health, /cache/clear
9. ✅ **Production-ready** - Gunicorn support, error handlers
10. ✅ **Never crashes** - All exceptions handled gracefully

## 📝 Example Use Cases

### Frontend Dashboard:
```javascript
fetch('http://localhost:5000/status')
  .then(r => r.json())
  .then(data => {
    console.log(`Parking: ${data.vehicle_count}/${100}`);
    console.log(`Status: ${data.status}`);
    console.log(`Trend: ${data.statistics.trend}`);
    if (data.anomaly) console.warn('ANOMALY!');
  });
```

### Mobile App:
```python
import requests
response = requests.get('http://localhost:5000/status/detailed')
status = response.json()
if status['error']:
    print(f"Error: {status['error_code']}")
else:
    occupancy = status['analysis']['occupancy_level']
    print(f"Occupancy: {occupancy}%")
```

### Monitoring/Alerts:
```python
# Alert if anomaly detected
data = requests.get('http://localhost:5000/status').json()
if data['anomaly']:
    send_email("PARKING LOT FULL!")
```

## 🔗 References

- [ThingSpeak API Docs](https://www.mathworks.com/help/thingspeak/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Groq API](https://console.groq.com/)
- [Gunicorn Deployment](https://gunicorn.org/)

---

**System Status:** ✅ Production-Ready | **Last Updated:** April 9, 2026
