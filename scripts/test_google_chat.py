import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def main():
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    model = os.getenv("GOOGLE_MODEL", "gemma-4-26b-a4b-it").strip()

    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing from your .env file.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {
            "parts": [{"text": "You are a supportive Persian wellness assistant. Reply only in Persian."}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": "امروز کمی مضطرب هستم. یک پیشنهاد ساده برای آرام شدن بده."}]}
        ],
        "generationConfig": {"temperature": 0.7},
    }

    print(f"Testing model: {model}\n")
    with httpx.Client(timeout=30) as client:
        r = client.post(url, json=payload)
        print(f"Status: {r.status_code}")
        r.raise_for_status()
        data = r.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    print("Model response:\n")
    print(text)


if __name__ == "__main__":
    main()