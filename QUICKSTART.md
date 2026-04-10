# 🚀 Quick Start - Smart Parking Dashboard

## One-Minute Setup

### 1️⃣ **Make sure Flask is running**
```bash
cd "c:\Users\Roshan Anand\Documents\Karunya\Semester-2\IOT\Micro Project"
python app.py
```

### 2️⃣ **Open your browser**
Go to: **http://localhost:5000/**

### 3️⃣ **Done!**
Dashboard is live and refreshing every 5 seconds.

---

## 📊 What You'll See

```
┌────────────────────────────────────────────┐
│ 🚗 Smart Parking Dashboard                 │
│ Last Updated: 2026-04-09T23:11:46          │
├────────────────────────────────────────────┤
│                                            │
│  📊 Current Vehicles    📈 Average Count   │
│        15                    12.4          │
│                                            │
│  📉 Trend                                  │
│  📈 Increasing                             │
│                                            │
├────────────────────────────────────────────┤
│ 🅿️  Parking Status: FREE ✅                │
│ Status: GREEN (parking available)          │
├────────────────────────────────────────────┤
│ 📋 Last 5 Entries:                         │
│ # 31: 16:46:35 - 0 vehicles - FREE        │
│ # 32: 16:47:00 - 0 vehicles - FREE        │
│ ...                                        │
└────────────────────────────────────────────┘

🔄 Refreshing every 5 seconds
```

---

## 🎨 Color Meanings

| Color | Status | Meaning |
|-------|--------|---------|
| 🟢 GREEN | FREE | Parking available - go ahead! |
| 🔴 RED | BUSY | Lot is full - try elsewhere |
| 🟡 YELLOW | ANOMALY | Danger! Count exceeds 20 |

---

## 📊 Dashboard Sections

| Section | Shows |
|---------|-------|
| **Header** | Title + last update time |
| **Vehicles Card** | Current count (0-100) |
| **Average Card** | Mean of last 5 values |
| **Trend Card** | Increasing/Decreasing/Stable |
| **Status Card** | BUSY/FREE with color badge |
| **Min/Max** | Range of recent values |
| **History Table** | Last 5 entries with timestamps |
| **Anomaly Alert** | Yellow warning if count > 20 |

---

## 🔧 Quick Changes

### **Speed up/slow down refresh**
Edit `templates/index.html` line 7:
```html
<meta http-equiv="refresh" content="5">
<!-- Change 5 to 10, 15, 30, etc (seconds) -->
```

### **Change anomaly threshold**
Edit `app.py` line 34:
```python
ANOMALY_THRESHOLD = 20  # Change to desired number
```

### **Change theme color**
Edit `templates/index.html` search for:
```css
color: #00d4ff;  /* Cyan - change to any hex color */
```

---

## 📡 Endpoints Cheat Sheet

```
Dashboard (Browser):     http://localhost:5000/
JSON API (JSON data):    http://localhost:5000/status
Detailed JSON:           http://localhost:5000/status/detailed
Health Check:            http://localhost:5000/health
```

---

## 🆘 Common Issues

### "Cannot connect to localhost:5000"
→ Flask app not running. Run: `python app.py`

### "No Data Available"
→ Check ThingSpeak API keys in `.env` file

### "Page doesn't refresh automatically"
→ Clear browser cache: Ctrl+Shift+Del then Ctrl+F5

### "Status shows wrong status"
→ Wait 5 seconds for auto-refresh, or manually refresh F5

---

## 📂 Files You Have

```
app.py                    ← Flask backend with "/" route
templates/
└── index.html           ← Dashboard UI (NO changes needed)
requirements.txt         ← Dependencies (already has Flask)
.env                     ← Your API keys
parking_system.log       ← Debug logs
```

---

## 🎯 Example Data

Typical response from ThingSpeak:

```json
{
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
  "history": [
    {
      "entry_id": "811786ad1ae74adfdd20dd0372abaaebc6246e343aebd01da0bfc4c02bf0106c",
      "display_entry_id": "81...6c",
      "serial_number": 35,
      "created_at": "2026-04-09T17:16:40Z",
      "vehicle_count": 15,
      "ai_decision": 0
    },
    ...
  ]
}
```

---

## ✅ Testing Checklist

- [ ] Flask app is running (`python app.py`)
- [ ] Opened http://localhost:5000/ in browser
- [ ] Dashboard shows header and title
- [ ] Vehicle count displays a number
- [ ] Status shows either BUSY or FREE
- [ ] Trend shows increasing/decreasing/stable
- [ ] History table shows last 5 entries
- [ ] Page refreshes on its own every 5 seconds

---

## 📞 What to Do Next

1. ✅ **Verify dashboard works** - Open in browser
2. 🧪 **Test with real data** - Add values to ThingSpeak
3. 📱 **Try on mobile** - Open on phone/tablet
4. 🎨 **Customize colors** - Edit CSS as needed
5. 🚀 **Deploy** - Use Gunicorn for production

---

## 🎓 Technical Stack

- **Backend:** Flask (Python)
- **Frontend:** HTML5 + CSS3 + Vanilla JS
- **API:** RESTful JSON endpoints
- **Cloud:** ThingSpeak IoT platform
- **Templating:** Jinja2 (Flask's template engine)
- **Database:** ThingSpeak (cloud)
- **AI:** Groq LLM (via smart_parking_ai.py)

---

## 🔗 Links

- **Dashboard Guide:** See `DASHBOARD_GUIDE.md`
- **Backend Guide:** See `BACKEND_GUIDE.md`
- **Full Details:** See `DASHBOARD_COMPLETE.md`

---

## 💡 Pro Tips

- 🖥️ Use full-screen browser for best experience
- 🔍 Check `parking_system.log` for debug info
- 📊 Add more vehicle counts to ThingSpeak to see status change
- ⚠️ Test anomaly by adding count > 20 to field3
- 💾 Dashboard is cached for 5 seconds (good for API limits)

---

**Status:** ✅ Dashboard LIVE and OPERATIONAL

**Next:** Open http://localhost:5000/ and enjoy! 🎉
