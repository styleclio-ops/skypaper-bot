import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# Meta Graph API Settings
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "skypaper_verify_secret_123")
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v21.0")
META_GRAPH_URL = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"

# Instagram Business Account ID (SkyPaper: 17841465176642948)
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "17841465176642948")

# Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Server Config
PORT = int(os.getenv("PORT", "8000"))
