"""
Label Studio auth helper.
Auto-exchanges the LS_REFRESH_TOKEN from .env for a short-lived access token.

Usage in any script:
    from annotation.ls_auth import get_ls_headers, LS_URL
    headers = get_ls_headers()
    requests.get(f"{LS_URL}/api/projects", headers=headers)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

LS_URL = "https://app.heartex.com"


def get_ls_headers() -> dict:
    refresh = os.environ["LS_REFRESH_TOKEN"]
    r = requests.post(f"{LS_URL}/api/token/refresh", json={"refresh": refresh})
    r.raise_for_status()
    access = r.json()["access"]
    return {"Authorization": f"Bearer {access}"}
