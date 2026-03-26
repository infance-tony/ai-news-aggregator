import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "app" / ".env")

if not os.getenv("OPENAI_API_KEY") and os.getenv("CEREBRAS_API_KEY"):
	os.environ["OPENAI_API_KEY"] = os.getenv("CEREBRAS_API_KEY")
