import os

# ===== Discord =====
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== OAuth =====
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# ===== Flask =====
PORT = int(os.getenv("PORT", 5000))
