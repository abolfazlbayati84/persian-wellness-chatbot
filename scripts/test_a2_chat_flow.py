# scripts/test_a2_chat_flow.py
import requests
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"


def pp(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def post(path, payload, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=60)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return r.status_code, data


def ensure_user_and_session():
    email = f"a2.test.{int(time.time() * 1000)}@example.com"
    password = "StrongPass123!"

    status, data = post(
        "/users",
        {"email": email, "password": password, "locale": "fa", "status": "active"},
    )
    if status != 201:
        pp("USER ERROR", data)
        sys.exit(1)
    user_id = data["id"]
    pp("USER CREATED", data)

    status, tdata = post("/auth/login", {"email": email, "password": password})
    if status != 200:
        pp("LOGIN ERROR", tdata)
        sys.exit(1)
    token = tdata["access_token"]
    pp("LOGIN OK", {"token_type": tdata.get("token_type")})

    status, sdata = post("/sessions", {"user_id": user_id}, token=token)
    if status != 200:
        pp("SESSION ERROR", sdata)
        sys.exit(1)
    pp("SESSION CREATED", sdata)

    return user_id, sdata["id"], token


def test_history_flow(session_id, token):
    turns = [
        "من چند شبه خوابم به‌هم ریخته و دیر می‌خوابم.",
        "روزها هم خسته‌ام و تمرکز ندارم.",
        "بر اساس همین چیزهایی که گفتم یه برنامه کوتاه ۳ مرحله‌ای بده.",
    ]

    last = None
    for i, t in enumerate(turns, start=1):
        if i > 1:
            time.sleep(2)  # avoid tripping AvalAI's per-minute rate limit during rapid testing
        status, data = post("/chat/turn", {"session_id": session_id, "user_text": t}, token=token)
        if status != 200:
            pp(f"TURN {i} ERROR", data)
            sys.exit(1)
        pp(f"TURN {i}", data)
        last = data

    text = last["assistant_message"]["content"]
    if len(text.strip()) < 20:
        print("[FAIL] assistant response too short.")
        sys.exit(1)
    if text.strip().startswith("Received:"):
        print("[FAIL] mock response detected (LLM_PROVIDER likely mock).")
        sys.exit(1)

    print("\n[PASS] History flow basic check passed.")


def test_severe_bypass(session_id, token):
    severe_text = "من میخوام به زندگیم پایان بدم"
    status, data = post("/chat/turn", {"session_id": session_id, "user_text": severe_text}, token=token)
    if status != 200:
        pp("SEVERE TURN ERROR", data)
        sys.exit(1)
    pp("SEVERE TURN", data)

    risk = data["assistant_message"].get("risk_tier")
    content = data["assistant_message"]["content"]

    if risk != "severe":
        print(f"[FAIL] expected risk_tier=severe, got {risk}")
        sys.exit(1)
    if "امنیت تو خیلی مهمه" not in content and "نمی‌تونم در آسیب‌زدن" not in content:
        print("[FAIL] severe bypass template not detected.")
        sys.exit(1)

    print("[PASS] Severe bypass check passed.")


if __name__ == "__main__":
    print(f"Testing A2 flow against {BASE_URL}")
    user_id, session_id, token = ensure_user_and_session()
    print(f"[INFO] user_id={user_id}, session_id={session_id}")

    test_history_flow(session_id, token)
    test_severe_bypass(session_id, token)

    print("\n✅ ALL A2 CHECKS PASSED")