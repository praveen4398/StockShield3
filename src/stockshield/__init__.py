"""StockShield 2.0 — Agentic Stock Analysis and Risk Intelligence System."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Set CrewAI / Local storage dir within workspace to prevent sandbox permission errors
_local_appdata = Path(__file__).resolve().parent.parent.parent / ".localappdata"
_local_appdata.mkdir(parents=True, exist_ok=True)
os.environ["LOCALAPPDATA"] = str(_local_appdata)
os.environ["CREWAI_STORAGE_DIR"] = str(_local_appdata / "crewai")

try:
    import yfinance as yf
    _yf_cache = _local_appdata / "py-yfinance"
    _yf_cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(_yf_cache))
except Exception:
    pass

# Search for .env in current directory, Backend directory, or workspace root
_candidates = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent.parent / ".env",
]
for _env in _candidates:
    if _env.exists():
        load_dotenv(dotenv_path=_env, override=True)
        break
else:
    load_dotenv()

__version__ = "2.0.0"
