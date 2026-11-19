import os
from dotenv import load_dotenv

load_dotenv()

PORTKEY_API_KEY = os.environ["PORTKEY_API_KEY"]
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_NAME", "@anthropic-prod/claude-sonnet-4-6")
MAX_FILE_CHARS = int(os.getenv("MAX_FILE_CHARS", "12000"))
POST_GITHUB_REVIEW = os.getenv("POST_GITHUB_REVIEW", "false").lower() == "true"
