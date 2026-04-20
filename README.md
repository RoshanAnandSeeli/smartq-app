# Smart Queue Management

An AI-assisted queue management app for entrepreneurship projects.

## Features
- Customer queue joining with Queue ID validation
- Supportive AI assistant while customers wait
- Admin dashboard with live queue status
- ETA tracking and discount controls
- Refresh Queue ID workflow for expiring old queues

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```

## Environment Variables
- `GROQ_API_KEY`
- `FLASK_SECRET_KEY`
- `PORT`

## Project Structure
- `app.py` - Flask backend
- `templates/index.html` - customer UI
- `templates/admin.html` - admin dashboard
- `templates/login.html` - admin access screen