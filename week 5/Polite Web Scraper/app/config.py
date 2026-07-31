import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory setup
BASE_DIR = Path(__file__).resolve().parent.parent

# Load configuration from .env file
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Configuration Variables
USER_AGENT = os.getenv("USER_AGENT", "BackendInternScraper/1.0 (+mailto:sibgha.mursaleen@example.com)")
DEFAULT_DELAY = float(os.getenv("DEFAULT_DELAY", "2.0"))

db_name = os.getenv("DATABASE_PATH", "wiki_backend_glossary.db")
DATABASE_PATH = BASE_DIR / db_name

# Target details
WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/"
WIKIPEDIA_ROBOTS_URL = "https://en.wikipedia.org/robots.txt"

# Default seed list of backend engineering concepts
SEED_CONCEPTS = [
    "Database",
    "Representational_state_transfer",
    "WebSocket",
    "Redis",
    "Docker_(software)",
    "SQLite",
    "FastAPI",
    "SQLAlchemy",
    "Web_server",
    "Application_programming_interface",
    "Microservices"
]
