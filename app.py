from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import requests
import json
import time
import threading
import uuid
import os
import sqlite3


def load_local_env():
    env_path = '.env'
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-me')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
DB_PATH = os.path.join(os.path.dirname(__file__), 'smartq.db')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')

ADMIN_SEED_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

twilio_client = None
queue_states = {}
whatsapp_sessions = {}  # from_number -> conversational session state


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password_hash TEXT NOT NULL,
            queue_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"]
    if count == 0:
        conn.execute(
            "INSERT INTO admins (password_hash, queue_id) VALUES (?, ?)",
            (generate_password_hash(ADMIN_SEED_PASSWORD), uuid.uuid4().hex[:8].upper())
        )
        conn.commit()
    conn.close()


def make_queue_state(queue_id):
    return {
        "queue_id": queue_id,
        "current_serving": 1,
        "last_token_issued": 1,
        "last_click_time": None,
        "service_history": [300],
        "user_satisfaction_scores": {},
        "users": {},
        "eta_offsets": {},
        "discounts": {},
        "game_scores": {}
    }


def load_queue_states():
    conn = get_db()
    rows = conn.execute("SELECT id, queue_id FROM admins").fetchall()
    conn.close()
    for row in rows:
        queue_states[row["id"]] = make_queue_state(row["queue_id"])


def get_admin_state(admin_id):
    state = queue_states.get(admin_id)
    if state:
        return state
    conn = get_db()
    row = conn.execute("SELECT queue_id FROM admins WHERE id = ?", (admin_id,)).fetchone()
    conn.close()
    if not row:
        return None
    queue_states[admin_id] = make_queue_state(row["queue_id"])
    return queue_states[admin_id]


def find_state_by_queue_id(queue_id):
    for admin_id, state in queue_states.items():
        if state["queue_id"] == queue_id:
            return admin_id, state
    return None, None


def parse_ai_json(raw_text, fallback_text):
    try:
        return json.loads(raw_text)
    except Exception:
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw_text[start:end + 1])
            except Exception:
                pass
    return {
        "text": fallback_text,
        "options": ["Play a game", "Tell me ETA", "Any tips?"],
        "satisfaction_score": 7
    }


def get_twilio_client():
    global twilio_client
    if twilio_client:
        return twilio_client
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_NUMBER:
        return None
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return twilio_client


def send_whatsapp_message(to_number, text):
    client = get_twilio_client()
    if not client:
        return False
    try:
        client.messages.create(
            body=text,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number
        )
        return True
    except Exception as e:
        print(f"[Twilio Send Error] {e}")
        return False


def notify_turn(state):
    token = state["current_serving"]
    for from_number, link in list(whatsapp_sessions.items()):
        if link.get("queue_id") == state["queue_id"] and int(link.get("token", 0)) == token:
            name = state["users"].get(str(token), "there")
            send_whatsapp_message(
                from_number,
                f"It is your turn now, {name}. Please proceed to the counter. Your WhatsApp session is now closed."
            )
            # Auto-close local chat linkage once the customer is called.
            del whatsapp_sessions[from_number]


def get_goodbye_message(name):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a warm, supportive queue assistant. Speak JSON only."},
            {"role": "user", "content": f"The customer named {name} has reached the counter. Reply as JSON: {{\"text\":\"...\"}}"}
        ],
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        content = r.json()['choices'][0]['message']['content']
        parsed = parse_ai_json(content, f"Thank you for waiting, {name}! You're up now.")
        return json.dumps({"text": parsed.get("text", f"Thank you for waiting, {name}! You're up now.")})
    except Exception:
        return json.dumps({"text": f"Thank you for your patience, {name}! You're all set."})


def get_groq_response(state, user_choice, queue_pos, token):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    tone = "encouraging and uplifting" if queue_pos < 3 else "empathetic and supportive"

    prompt = f"""
Queue Position: {queue_pos} people ahead. User chose: '{user_choice}'.
Tone: {tone}
Return valid JSON only with keys: text, options, satisfaction_score.
Keep options short (max 3).
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are a warm, helpful queue assistant. Always return strict JSON."
            },
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    fallback = {
        "text": "We appreciate your patience. Want to play a quick game or check your ETA?",
        "options": ["Play Snake", "Check ETA", "Any updates?"],
        "satisfaction_score": 7
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        raw = r.json()['choices'][0]['message']['content']
        data = parse_ai_json(raw, fallback["text"])
    except Exception as e:
        print(f"AI Error: {e}")
        data = fallback

    score = int(data.get("satisfaction_score", 7))
    score = max(1, min(10, score))
    state["user_satisfaction_scores"][str(token)] = score

    return json.dumps({
        "text": data.get("text", fallback["text"]),
        "options": data.get("options", fallback["options"]),
        "satisfaction_score": score
    })


def current_admin_state():
    admin_id = session.get('admin_id')
    if not admin_id:
        return None, None
    return admin_id, get_admin_state(admin_id)


init_db()
load_queue_states()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        conn = get_db()
        rows = conn.execute("SELECT id, password_hash FROM admins").fetchall()
        conn.close()
        for row in rows:
            if check_password_hash(row["password_hash"], password):
                session['admin_id'] = row["id"]
                return redirect(url_for('admin'))
        error = "Invalid password"
    return render_template('login.html', error=error)


@app.route('/admin')
def admin():
    admin_id, state = current_admin_state()
    if not admin_id or not state:
        return redirect(url_for('login'))
    return render_template('admin.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/admin_passwords', methods=['POST'])
def add_admin_password():
    admin_id, _ = current_admin_state()
    if not admin_id:
        return "Unauthorized", 403
    password = request.json.get('password', '').strip()
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

    queue_id = uuid.uuid4().hex[:8].upper()
    conn = get_db()
    conn.execute(
        "INSERT INTO admins (password_hash, queue_id) VALUES (?, ?)",
        (generate_password_hash(password), queue_id)
    )
    new_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()

    queue_states[new_id] = make_queue_state(queue_id)
    return jsonify({"success": True, "queue_id": queue_id})


@app.route('/api/queue_exists')
def queue_exists():
    queue_id = request.args.get('queue_id', '').upper().strip()
    if not queue_id:
        return jsonify({"valid": False})
    _, state = find_state_by_queue_id(queue_id)
    return jsonify({"valid": state is not None})


@app.route('/api/join', methods=['POST'])
def join_queue():
    name = request.json.get('name', 'Anonymous').strip() or 'Anonymous'
    queue_id = request.json.get('queue_id', '').upper().strip()
    _, state = find_state_by_queue_id(queue_id)
    if not state:
        return jsonify({"error": "Queue not found", "code": "queue_not_found"}), 404

    state["last_token_issued"] += 1
    new_token = state["last_token_issued"]
    state["users"][str(new_token)] = name
    if state["last_click_time"] is None:
        state["last_click_time"] = time.time()
    return jsonify({"token": new_token, "name": name, "queue_id": state["queue_id"]})


@app.route('/api/status')
def status():
    token_arg = request.args.get('token', '0')
    queue_id = request.args.get('queue_id', '').upper().strip()
    user_token = int(token_arg) if str(token_arg).isdigit() else 0

    state = None
    if queue_id:
        _, state = find_state_by_queue_id(queue_id)
    else:
        _, state = current_admin_state()

    if not state:
        return jsonify({"error": "Queue not found", "code": "queue_not_found"}), 404

    if user_token > 0 and str(user_token) not in state["users"] and user_token >= state["current_serving"]:
        return jsonify({"error": "Queue not found", "code": "queue_not_found"}), 404

    ahead = max(0, user_token - state["current_serving"])
    avg_seconds = sum(state["service_history"]) / len(state["service_history"])
    base_eta = round((ahead * avg_seconds) / 60, 1)
    offset = state["eta_offsets"].get(str(user_token), 0)
    dynamic_eta = round(max(0, base_eta + offset), 1)

    current_satisfaction = state["user_satisfaction_scores"].get(str(state["current_serving"]), 8)
    user_satisfaction = state["user_satisfaction_scores"].get(str(user_token), 8)
    has_queue = state["last_token_issued"] > state["current_serving"]
    elapsed = round(time.time() - state["last_click_time"], 1) if (state["last_click_time"] and has_queue) else None

    return jsonify({
        "current": state["current_serving"],
        "last_token": state["last_token_issued"],
        "avg_seconds": round(avg_seconds, 1),
        "eta": dynamic_eta,
        "satisfaction": user_satisfaction,
        "current_satisfaction": current_satisfaction,
        "discount": state["discounts"].get(str(user_token), None),
        "elapsed_seconds": elapsed,
        "serving_token": state["current_serving"],
        "queue_id": state["queue_id"]
    })


@app.route('/api/queue_list')
def queue_list():
    admin_id, state = current_admin_state()
    if not admin_id or not state:
        return "Unauthorized", 403

    avg_seconds = sum(state["service_history"]) / len(state["service_history"])
    members = []
    for token_str, name in state["users"].items():
        t = int(token_str)
        if t < state["current_serving"]:
            continue
        ahead = max(0, t - state["current_serving"])
        base_eta = round((ahead * avg_seconds) / 60, 1)
        offset = state["eta_offsets"].get(token_str, 0)
        eta = round(max(0, base_eta + offset), 1)
        members.append({
            "token": t,
            "name": name,
            "satisfaction": state["user_satisfaction_scores"].get(token_str, 8),
            "eta": eta,
            "is_current": t == state["current_serving"],
            "game": state["game_scores"].get(token_str),
            "queue_id": state["queue_id"]
        })
    members.sort(key=lambda x: x["token"])
    return jsonify({"members": members, "queue_id": state["queue_id"]})


@app.route('/api/refresh_queue_id', methods=['POST'])
def refresh_queue_id():
    admin_id, state = current_admin_state()
    if not admin_id or not state:
        return "Unauthorized", 403

    old_queue_id = state["queue_id"]
    new_queue_id = uuid.uuid4().hex[:8].upper()

    conn = get_db()
    conn.execute("UPDATE admins SET queue_id = ? WHERE id = ?", (new_queue_id, admin_id))
    conn.commit()
    conn.close()

    queue_states[admin_id] = make_queue_state(new_queue_id)

    for number, link in list(whatsapp_sessions.items()):
        if link.get("queue_id") == old_queue_id:
            del whatsapp_sessions[number]

    return jsonify({"success": True, "old_queue_id": old_queue_id, "new_queue_id": new_queue_id})


@app.route('/api/adjust_eta', methods=['POST'])
def adjust_eta():
    _, state = current_admin_state()
    if not state:
        return "Unauthorized", 403
    token = str(request.json.get('token'))
    delta = float(request.json.get('delta', 0))
    state["eta_offsets"][token] = state["eta_offsets"].get(token, 0) + delta
    return jsonify({"success": True})


@app.route('/api/game_score', methods=['POST'])
def game_score():
    queue_id = request.json.get('queue_id', '').upper().strip()
    _, state = find_state_by_queue_id(queue_id)
    if not state:
        return jsonify({"error": "Queue not found", "code": "queue_not_found"}), 404

    token = str(request.json.get('token'))
    score = int(request.json.get('score', 0))
    playing = bool(request.json.get('playing', False))
    state["game_scores"][token] = {"score": score, "playing": playing}
    threshold = 200
    if score >= threshold and token not in state["discounts"]:
        state["discounts"][token] = 10
    return jsonify({"success": True, "discount_threshold": threshold})


@app.route('/api/adjust_avg', methods=['POST'])
def adjust_avg():
    _, state = current_admin_state()
    if not state:
        return "Unauthorized", 403

    delta_seconds = float(request.json.get('delta', 0))
    current_avg = sum(state["service_history"]) / len(state["service_history"])
    state["service_history"].append(max(30, current_avg + delta_seconds))
    if len(state["service_history"]) > 5:
        state["service_history"].pop(0)
    avg_seconds = round(sum(state["service_history"]) / len(state["service_history"]), 1)
    return jsonify({"avg_seconds": avg_seconds})


@app.route('/api/apply_discount', methods=['POST'])
def apply_discount():
    _, state = current_admin_state()
    if not state:
        return "Unauthorized", 403
    token = str(request.json.get('token'))
    percent = int(request.json.get('percent'))
    state["discounts"][token] = percent
    return jsonify({"success": True})


@app.route('/api/goodbye', methods=['POST'])
def goodbye():
    queue_id = request.json.get('queue_id', '').upper().strip()
    token = str(request.json.get('token'))
    _, state = find_state_by_queue_id(queue_id)
    if not state:
        return jsonify({"text": "Queue not found."}), 404
    name = state["users"].get(token, "friend")
    return get_goodbye_message(name)


@app.route('/api/interact', methods=['POST'])
def interact():
    data = request.json
    choice = data.get('choice', 'status update')
    token = str(data.get('token'))
    queue_id = data.get('queue_id', '').upper().strip()
    _, state = find_state_by_queue_id(queue_id)
    if not state:
        return jsonify({"error": "Queue not found", "code": "queue_not_found"}), 404
    pos = int(token) - state["current_serving"]
    return get_groq_response(state, choice, pos, token)


@app.route('/api/next', methods=['POST'])
def next_queue():
    _, state = current_admin_state()
    if not state:
        return "Unauthorized", 403

    now = time.time()
    if state["last_click_time"]:
        duration = now - state["last_click_time"]
        state["service_history"].append(duration)
        if len(state["service_history"]) > 5:
            state["service_history"].pop(0)

    state["last_click_time"] = now
    state["current_serving"] += 1
    notify_turn(state)
    return jsonify({"success": True})


@app.route('/twilio/whatsapp', methods=['POST'])
@app.route('/twilio/whatsapp/', methods=['POST'])
def twilio_whatsapp():
    from_number = request.values.get('From', '').strip()
    body = request.values.get('Body', '').strip()
    lower = body.lower()

    response = MessagingResponse()

    def twiml_reply():
        return Response(str(response), mimetype='application/xml')

    def available_queue_ids():
        ids = sorted({s["queue_id"] for s in queue_states.values()})
        return ids

    def build_queue_menu(ids):
        lines = ["Available queues:"]
        for i, qid in enumerate(ids, start=1):
            lines.append(f"{i}. {qid}")
        return "\n".join(lines)

    if lower in ('hi', 'hello', 'start', 'menu'):
        queues = available_queue_ids()
        if not queues:
            response.message("No active queues are available right now. Please try again shortly.")
            return twiml_reply()
        whatsapp_sessions[from_number] = {
            "stage": "awaiting_queue",
            "menu": queues
        }
        response.message(
            "Welcome to SmartQ WhatsApp Assistant.\n"
            "Instructions:\n"
            "1) Choose a queue from the list by number or queue id.\n"
            "2) Then send your token number.\n"
            "3) After linking, use: status or ai <message>.\n\n"
            + build_queue_menu(queues)
        )
        return twiml_reply()

    if lower.startswith('link '):
        parts = body.split()
        if len(parts) < 3:
            response.message("Usage: link <QUEUE_ID> <TOKEN>")
            return twiml_reply()
        queue_ref = parts[1].strip()
        token = parts[2].strip()
        queue_id = queue_ref.upper()

        # Allow selecting queue by serial number in direct link mode too.
        if queue_ref.isdigit():
            queues = available_queue_ids()
            idx = int(queue_ref)
            if 1 <= idx <= len(queues):
                queue_id = queues[idx - 1]

        _, state = find_state_by_queue_id(queue_id)
        if not state or token not in state["users"]:
            response.message("Invalid queue id or token.")
            return twiml_reply()
        whatsapp_sessions[from_number] = {"queue_id": queue_id, "token": int(token)}
        name = state["users"].get(token, "there")
        response.message(
            f"Linked successfully. Welcome, {name}! Send 'status' for queue position or 'ai <message>' to chat."
        )
        return twiml_reply()

    session_link = whatsapp_sessions.get(from_number)
    if not session_link:
        response.message("Send 'hi' to start and link your queue.")
        return twiml_reply()

    stage = session_link.get("stage")
    if stage == "awaiting_queue":
        menu = session_link.get("menu", [])
        selected_queue = None

        if body.isdigit():
            idx = int(body)
            if 1 <= idx <= len(menu):
                selected_queue = menu[idx - 1]
        else:
            typed_queue = body.upper().strip()
            if typed_queue in menu:
                selected_queue = typed_queue

        if not selected_queue:
            response.message("Invalid queue selection. Reply with a queue number or queue id from the menu.")
            return twiml_reply()

        session_link["stage"] = "awaiting_token"
        session_link["queue_id"] = selected_queue
        session_link.pop("menu", None)
        whatsapp_sessions[from_number] = session_link
        response.message(f"Selected queue {selected_queue}. Now send your token number.")
        return twiml_reply()

    if stage == "awaiting_token":
        token_raw = body.strip()
        if not token_raw.isdigit():
            response.message("Please send only your token number (example: 7).")
            return twiml_reply()

        token = int(token_raw)
        queue_id = session_link.get("queue_id", "")
        _, state = find_state_by_queue_id(queue_id)
        if not state or str(token) not in state["users"]:
            response.message("Token not found for that queue. Please check and send your token again.")
            return twiml_reply()

        whatsapp_sessions[from_number] = {"queue_id": queue_id, "token": token}
        name = state["users"].get(str(token), "there")
        response.message(
            f"Linked successfully. Welcome, {name}! Send 'status' for queue position or 'ai <message>' to chat."
        )
        return twiml_reply()

    queue_id = session_link["queue_id"]
    token = int(session_link["token"])
    _, state = find_state_by_queue_id(queue_id)
    if not state:
        response.message("Queue not found or expired. Please relink with a new queue id.")
        return twiml_reply()

    if lower == 'status':
        ahead = max(0, token - state["current_serving"])
        avg_seconds = sum(state["service_history"]) / len(state["service_history"])
        eta = round((ahead * avg_seconds) / 60, 1)
        if token <= state["current_serving"]:
            response.message("It is your turn now.")
        else:
            response.message(f"Queue {queue_id}: {ahead} ahead of you, ETA ~{eta} min.")
        return twiml_reply()

    if lower.startswith('ai'):
        text = body[2:].strip() if len(body) > 2 else "How is my queue moving?"
        raw = get_groq_response(state, text, token - state["current_serving"], token)
        data = parse_ai_json(raw, "You're doing great. Your turn is coming soon.")
        response.message(data.get("text", "You're doing great. Your turn is coming soon."))
        return twiml_reply()

    response.message("Commands: status | ai <message> | link <QUEUE_ID> <TOKEN>")
    return twiml_reply()


def auto_advance_worker():
    while True:
        time.sleep(10)
        try:
            for state in queue_states.values():
                current = state["current_serving"]
                last = state["last_token_issued"]
                if current > last:
                    continue
                avg_seconds = sum(state["service_history"]) / len(state["service_history"])
                offset = state["eta_offsets"].get(str(current), 0)
                if state["last_click_time"] is None:
                    continue
                time_at_counter = time.time() - state["last_click_time"]
                allowed = avg_seconds + (offset * 60)
                if time_at_counter >= allowed:
                    now = time.time()
                    duration = now - state["last_click_time"]
                    state["service_history"].append(duration)
                    if len(state["service_history"]) > 5:
                        state["service_history"].pop(0)
                    state["last_click_time"] = now
                    state["current_serving"] += 1
                    notify_turn(state)
        except Exception as e:
            print(f"[Auto-Advance Error] {e}")


auto_thread = threading.Thread(target=auto_advance_worker, daemon=True)
auto_thread.start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)