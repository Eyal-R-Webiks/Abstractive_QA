import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
api_key = os.environ.get("OPENROUTER_API_KEY")

if not api_key:
    print("Error: OPENROUTER_API_KEY not found in .env")
    exit(1)

headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    response = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
    response.raise_for_status()
    data = response.json()
    
    # OpenRouter auth/key endpoint returns data about the key, including limit and usage.
    # We can also check https://openrouter.ai/api/v1/credits
    print("Key Auth Data:", data)
except Exception as e:
    print(f"Error checking key info: {e}")

try:
    # also try credits endpoint just in case
    credit_res = requests.get("https://openrouter.ai/api/v1/credits", headers=headers)
    if credit_res.status_code == 200:
        print("Credits Data:", credit_res.json())
except Exception as e:
    pass

