import os
from os.path import join, dirname
from dotenv import load_dotenv

load_dotenv(join(dirname(__file__), '../.env'), verbose=True)

# ===== Discord =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ===== OAuth =====
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# # ===== Flask =====
# PORT = int(os.getenv("PORT", 5000))
