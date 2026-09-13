import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def main():
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing from your .env file.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    with httpx.Client(timeout=30) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()

    models = data.get("models", [])
    print(f"Found {len(models)} total models for this API key.\n")
    print("Models that support generateContent (usable for chat):\n")
    for m in models:
        name = m.get("name", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            print(f"- {name}")


if __name__ == "__main__":
    main()