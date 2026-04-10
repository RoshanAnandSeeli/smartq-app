import os
import time
import requests
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

# --- Config ---
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "<your_groq_api_key>")
TS_READ_KEY   = os.environ.get("THINGSPEAK_READ_KEY", "<your_read_key>")
TS_WRITE_KEY  = os.environ.get("THINGSPEAK_WRITE_KEY", "<your_write_key>")
TS_CHANNEL_ID = os.environ.get("THINGSPEAK_CHANNEL_ID", "<your_channel_id>")

GROQ_MODEL     = "llama-3.3-70b-versatile"
POLL_INTERVAL  = 20   # seconds
BUSY_THRESHOLD = 5    # fallback rule: avg count > this → Busy
MAX_RETRIES    = 3    # max retries for API calls
RETRY_DELAY    = 3    # seconds between retries


def request_with_retry(method, url, **kwargs):
    """HTTP request with up to MAX_RETRIES attempts and timeout enforcement."""
    kwargs.setdefault("timeout", 10)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            print(f"[RETRY {attempt}/{MAX_RETRIES}] Request timed out: {url}")
        except requests.exceptions.RequestException as e:
            print(f"[RETRY {attempt}/{MAX_RETRIES}] Request failed: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    raise RuntimeError(f"All {MAX_RETRIES} attempts failed for {url}")


def get_data():
    """Fetch last 5 entries from ThingSpeak and return vehicle counts from field3."""
    url = f"https://api.thingspeak.com/channels/{TS_CHANNEL_ID}/fields/3.json"
    response = request_with_retry("GET", url, params={"api_key": TS_READ_KEY, "results": 5})

    feeds = response.json().get("feeds", [])
    if not feeds:
        raise ValueError("No data returned from ThingSpeak.")

    counts = [int(f["field3"]) for f in feeds if f.get("field3") is not None]
    if not counts:
        raise ValueError("field3 is empty in all fetched entries.")

    print(f"[DATA] Vehicle counts (last {len(counts)}): {counts}")
    return counts


def fallback_decision(counts):
    """Simple rule-based fallback when Groq API is unavailable."""
    avg = sum(counts) / len(counts)
    status = "Busy" if avg > BUSY_THRESHOLD else "Free"
    allow  = "NO"   if status == "Busy"      else "YES"
    print(f"[FALLBACK] avg={avg:.1f} → STATUS={status} | ALLOW={allow}")
    return status, allow  # reason is added by ask_ai caller


def parse_ai_response(reply):
    """Safely extract STATUS, ALLOW and REASON from LLM response text."""
    status, allow, reason = None, None, None
    for line in reply.splitlines():
        line = line.strip()
        if line.upper().startswith("STATUS:"):
            val = line.split(":", 1)[1].strip().capitalize()
            if val in ("Busy", "Free"):
                status = val
        elif line.upper().startswith("ALLOW:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("YES", "NO"):
                allow = val
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    if not status or not allow:
        raise ValueError(f"Could not parse AI response: {reply}")
    reason = reason or "No reason provided"
    return status, allow, reason


def ask_ai(counts):
    """Send vehicle counts to Groq LLM; fall back to rule-based on any failure."""
    prompt = (
        f"You are a smart parking system AI.\n"
        f"Recent vehicle counts in the parking lot: {counts}\n"
        f"Based on this data, determine if the parking lot is busy or free.\n"
        f"Respond ONLY in this exact format:\n"
        f"STATUS: Busy\nALLOW: NO\nREASON: <short explanation>\n"
        f"or\n"
        f"STATUS: Free\nALLOW: YES\nREASON: <short explanation>"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                timeout=15,
            )
            reply = response.choices[0].message.content.strip()
            print(f"[AI] Response:\n{reply}")
            status, allow, reason = parse_ai_response(reply)
            print(f"[REASON] {reason}")
            return status, allow, reason
        except ValueError as e:
            print(f"[RETRY {attempt}/{MAX_RETRIES}] Bad AI response: {e}")
        except Exception as e:
            print(f"[RETRY {attempt}/{MAX_RETRIES}] Groq error: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print("[FALLBACK] Groq unavailable after retries. Using rule-based decision.")
    status, allow = fallback_decision(counts)
    return status, allow, "Groq unavailable — rule-based fallback used"


def send_result(status):
    """Send field4 = 1 if Busy, 0 if Free to ThingSpeak."""
    field4_value = 1 if status == "Busy" else 0
    response = request_with_retry(
        "GET", "https://api.thingspeak.com/update",
        params={"api_key": TS_WRITE_KEY, "field4": field4_value}
    )
    if response.text.strip() == "0":
        raise RuntimeError("ThingSpeak write failed (returned 0). Check write key or rate limit.")
    print(f"[SENT] field4 = {field4_value} (Status: {status})")


def main():
    print("[START] Smart Parking AI loop started.")
    while True:
        try:
            counts = get_data()
            status, allow, reason = ask_ai(counts)
            print(f"[DECISION] STATUS={status} | ALLOW={allow} | REASON={reason}")
            send_result(status)
        except RuntimeError as e:
            print(f"[ERROR] {e}")
        except ValueError as e:
            print(f"[ERROR] Data issue: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected: {e}")
        finally:
            print(f"[WAIT] Sleeping {POLL_INTERVAL}s...\n")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
