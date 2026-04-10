# 📊 Smart Parking Dashboard - Quick Guide

## 🎯 Overview

Your Flask app now includes a beautiful, modern real-time dashboard accessible at `http://localhost:5000/` (root path).

## 🚀 Quick Start

### 1. **Verify the Flask app is running**
```bash
cd "c:\Users\Roshan Anand\Documents\Karunya\Semester-2\IOT\Micro Project"
python app.py
```

You should see:
```
Smart Parking System Flask Backend Starting
Running on http://127.0.0.1:5000
```

### 2. **Open the Dashboard**
Navigate to: **`http://localhost:5000/`** in your web browser

## 📺 Dashboard Features

### A. **Header Section**
- 🚗 Title: "Smart Parking Dashboard"
- 📝 Subtitle: "IoT + AI + Cloud System"
- ⏱️ Last updated timestamp (ISO 8601 format)

### B. **Main Cards** (Real-time Data)

| Card | Shows | Value |
|------|-------|-------|
| 📊 Current Vehicles | Live vehicle count | 0-100 |
| 📈 Average Count | Mean of last 5 values | Decimal number |
| 📉 Trend | Direction of change | Increasing / Decreasing / Stable |
| 🅿️ Parking Status | Current availability | BUSY (Red) / FREE (Green) |
| 📊 Min/Max Counts | Range in history | Min and Max values |

### C. **Color Coding**

```
✅ FREE (Green)
   - Parking lots have available spaces
   - Status badge shows "✅ PARKING AVAILABLE"
   - Card background: Subtle green glow

❌ BUSY (Red)
   - Parking lot is full
   - Status badge shows "🚫 PARKING FULL"
   - Card background: Subtle red glow

⚠️ ANOMALY (Yellow Warning)
   - Vehicle count exceeds 20 (threshold)
   - Shows "ANOMALY DETECTED" warning banner
   - Indicates system alert condition
```

### D. **History Table**
Shows the last 5 entries from ThingSpeak with:
- Entry ID
- Timestamp (ISO format)
- Vehicle count at that time
- Status at that time (BUSY/FREE)

### E. **Auto-Refresh**
- Dashboard **automatically refreshes every 5 seconds**
- Controlled by meta tag: `<meta http-equiv="refresh" content="5">`
- Shows most recent data from ThingSpeak API

## 🎨 Visual Design

### Theme
- **Dark Mode**: Professional dark blue gradient background
- **Modern Cards**: Glassmorphism effect with blur backdrop
- **Neon Accents**: Cyan (#00d4ff) highlights with glow effects
- **Smooth Transitions**: Hover animations and transitions

### Responsive
- ✅ Works on Desktop (Full featured)
- ✅ Works on Tablet (Adjusted layout)
- ✅ Works on Mobile (Single column)

## 📡 Data Flow

```
ThingSpeak Cloud
      ↓
Flask Backend (/status API)
      ↓
get_thingspeak_data()
      ↓
Validates & Cleans Data
      ↓
Computes Statistics
      ↓
Renders index.html Template
      ↓
Browser Displays Dashboard
      ↓
Auto-refresh every 5 seconds
```

## 🛡️ Error Handling

If ThingSpeak is unavailable:
- Dashboard displays "⚠️ System Error" alert
- Shows error message with details
- All cards show "—" (No data available)
- No crashes - graceful degradation

## 📊 Example Scenarios

### Scenario 1: Lot is FREE
```
Current Vehicles: 5
Status: FREE (Green badge)
Average: 4.8
Trend: Increasing
Anomaly: OFF (No warning)
```

### Scenario 2: Lot is BUSY
```
Current Vehicles: 85
Status: BUSY (Red badge)
Average: 75.2
Trend: Increasing
Anomaly: ON (Yellow warning - exceeds threshold)
```

### Scenario 3: No Data
```
Current Vehicles: — (No data)
Status: — (No status data available)
Average: — (No data available)
History: No historical data available yet
```

## 🔧 Customization

### Change Auto-Refresh Rate
Edit line 7 in `templates/index.html`:
```html
<!-- Default: 5 seconds -->
<meta http-equiv="refresh" content="5">

<!-- To change to 10 seconds: -->
<meta http-equiv="refresh" content="10">
```

### Change Anomaly Threshold
Edit line 34 in `app.py`:
```python
# Default: 20 vehicles
ANOMALY_THRESHOLD = 20

# Change to 30:
ANOMALY_THRESHOLD = 30
```

### Customize Colors
Edit CSS in `templates/index.html` starting at line 100:
```css
/* Change primary accent color */
color: #00d4ff;  /* Cyan - change to any hex color */

/* Change background gradient */
background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
```

## 📱 Endpoints Summary

| URL | Type | Purpose |
|-----|------|---------|
| `/` | GET | **Dashboard HTML** (THIS IS NEW!) |
| `/status` | GET | JSON API (raw data) |
| `/status/detailed` | GET | JSON with analysis |
| `/health` | GET | Health check |
| `/cache/clear` | POST | Clear cache (debug) |

## 🚨 Troubleshooting

### "Port 5000 is already in use"
```bash
# Kill existing Flask process
taskkill /IM python.exe /F

# Or use different port
python app.py --port 5001
```

### Dashboard shows "No Data Available"
- Check if `.env` file has correct ThingSpeak credentials
- Verify ThingSpeak API keys are valid
- Check internet connection

### Dashboard doesn't auto-refresh
- Clear browser cache (Ctrl+Shift+Del)
- Check browser console for errors (F12)
- Verify Flask app is still running

## 📊 Real-World Testing

### To test with sample data:

1. **Add via ThingSpeak Web Interface**
   - Go to your ThingSpeak channel
   - Manually add values to field3 (vehicle count)
   
2. **Or use curl from PowerShell:**
   ```powershell
   $url = "https://api.thingspeak.com/update?api_key=<YOUR_WRITE_KEY>&field3=15"
   Invoke-WebRequest -Uri $url
   ```

3. **Watch the dashboard update** (5-second refresh)

## 🎯 Key Features Recap

✅ **Modern UI** - Dark theme with neon accents  
✅ **Real-time Data** - Updates every 5 seconds  
✅ **Color Coding** - Instant visual feedback (Red/Green/Yellow)  
✅ **Auto-refresh** - No manual page reloads needed  
✅ **Responsive** - Works on all devices  
✅ **Error Handling** - Never crashes, shows fallback messages  
✅ **History Table** - See last 5 entries  
✅ **Statistics** - Min, Max, Average, Trend  
✅ **Anomaly Warning** - Alert on dangerous conditions  
✅ **Mobile Friendly** - Optimized for all screen sizes  

## 🔗 Integration Points

### Dashboard reads from:
- Flask route `/` (renders template)
- Function `get_thingspeak_data()` (fetches/validates data)
- File `templates/index.html` (UI template)

### Data is passed to template as:
```python
{
  "timestamp": "2026-04-09T23:11:46.774995",
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
  "history": [...],
  "error": null,
  "error_code": null
}
```

## 📝 Notes

- The dashboard uses **Flask's `render_template()`** to inject Python data into HTML
- Jinja2 templating handles missing data gracefully
- No JavaScript frameworks (React/Vue) needed - pure vanilla JS
- Optimized for demo/educational purposes (production-ready)
- All styling is inline CSS (no external dependencies)

---

**Status:** ✅ COMPLETE | **Quality:** Production-Ready | **Theme:** Dark Modern Design

