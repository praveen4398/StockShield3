"""Security and input validation guardrails for StockShield 2.0."""

import re
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

COMPANY_NAME_TO_TICKER = {
    "TATA STEEL": "TATASTEEL",
    "TATA MOTORS": "TATAMOTORS",
    "TCS": "TCS",
    "TATA CONSULTANCY SERVICES": "TCS",
    "TATA POWER": "TATAPOWER",
    "TATA CONSUMER": "TATACONSUM",
    "TATA CONSUMER PRODUCTS": "TATACONSUM",
    "TATA TECHNOLOGIES": "TATATECH",
    "TRENT": "TRENT",
    "TITAN": "TITAN",
    "TITAN COMPANY": "TITAN",
    "RELIANCE": "RELIANCE",
    "RELIANCE INDUSTRIES": "RELIANCE",
    "JIO FINANCIAL": "JIOFIN",
    "JIO FINANCIAL SERVICES": "JIOFIN",
    "HDFC": "HDFCBANK",
    "HDFC BANK": "HDFCBANK",
    "HDFCBANK": "HDFCBANK",
    "INFOSYS": "INFY",
    "INFY": "INFY",
    "ICICI": "ICICIBANK",
    "ICICI BANK": "ICICIBANK",
    "ICICIBANK": "ICICIBANK",
    "SBI": "SBIN",
    "STATE BANK OF INDIA": "SBIN",
    "STATE BANK": "SBIN",
    "SBIN": "SBIN",
    "WIPRO": "WIPRO",
    "BAJAJ FINANCE": "BAJFINANCE",
    "BAJFINANCE": "BAJFINANCE",
    "BAJAJ FINSERV": "BAJAJFINSV",
    "BAJAJ AUTO": "BAJAJ-AUTO",
    "BHARTI AIRTEL": "BHARTIARTL",
    "AIRTEL": "BHARTIARTL",
    "LARSEN & TOUBRO": "LT",
    "LARSEN AND TOUBRO": "LT",
    "L&T": "LT",
    "LT": "LT",
    "HINDUSTAN UNILEVER": "HINDUNILVR",
    "HUL": "HINDUNILVR",
    "ITC": "ITC",
    "ITC LIMITED": "ITC",
    "ASIAN PAINTS": "ASIANPAINT",
    "MARUTI": "MARUTI",
    "MARUTI SUZUKI": "MARUTI",
    "SUN PHARMA": "SUNPHARMA",
    "CIPLA": "CIPLA",
    "DR REDDY": "DRREDDY",
    "DR REDDYS": "DRREDDY",
    "DR REDDY'S": "DRREDDY",
    "APOLLO HOSPITALS": "APOLLOHOSP",
    "DIVIS LAB": "DIVISLAB",
    "DIVIS LABORATORIES": "DIVISLAB",
    "AXIS BANK": "AXISBANK",
    "KOTAK": "KOTAKBANK",
    "KOTAK BANK": "KOTAKBANK",
    "KOTAK MAHINDRA BANK": "KOTAKBANK",
    "NTPC": "NTPC",
    "POWER GRID": "POWERGRID",
    "ONGC": "ONGC",
    "COAL INDIA": "COALINDIA",
    "ADANI ENTERPRISES": "ADANIENT",
    "ADANI PORTS": "ADANIPORTS",
    "ADANI POWER": "ADANIPOWER",
    "ADANI GREEN": "ADANIGREEN",
    "ULTRATECH CEMENT": "ULTRACEMCO",
    "ULTRATECH": "ULTRACEMCO",
    "GRASIM": "GRASIM",
    "JSW STEEL": "JSWSTEEL",
    "HINDALCO": "HINDALCO",
    "VEDANTA": "VEDL",
    "TECH MAHINDRA": "TECHM",
    "HCL TECH": "HCLTECH",
    "HCL TECHNOLOGIES": "HCLTECH",
    "EICHER MOTORS": "EICHERMOT",
    "HERO MOTOCORP": "HEROMOTOCO",
    "BRITANNIA": "BRITANNIA",
    "NESTLE": "NESTLEIND",
    "NESTLE INDIA": "NESTLEIND",
    "BHARAT ELECTRONICS": "BEL",
    "BEL": "BEL",
    "HINDUSTAN AERONAUTICS": "HAL",
    "HAL": "HAL",
    "BHEL": "BHEL",
    "DLF": "DLF",
    "ZOMATO": "ZOMATO",
    "SWIGGY": "SWIGGY",
    "PAYTM": "PAYTM",
    "IRCTC": "IRCTC",
    "RVNL": "RVNL",
    "IRFC": "IRFC",
    "SUZLON": "SUZLON",
    "PNB": "PNB",
    "PUNJAB NATIONAL BANK": "PNB",
    "BANK OF BARODA": "BANKBARODA",
    "FEDERAL BANK": "FEDERALBNK",
    "IDFC FIRST BANK": "IDFCFIRSTB",
    "YES BANK": "YESBANK",
    "INDUSIND BANK": "INDUSINDBK",
    "BPCL": "BPCL",
    "IOC": "IOC",
    "INDIAN OIL": "IOC",
    "HPCL": "HPCL",
    "SAIL": "SAIL",
    "VBL": "VBL",
    "VARUN BEVERAGES": "VBL",
    "PIDILITE": "PIDILITIND",
    "HAVELLS": "HAVELLS",
    "SIEMENS": "SIEMENS",
    "ABB": "ABB"
}

ALLOWED_TICKERS = {"TCS.NS", "INFY.NS", "RELIANCE.NS"}
MAX_LOOKBACK_DAYS = 500
MIN_LOOKBACK_DAYS = 10
MAX_PROMPT_LENGTH = 1000

# Deterministic patterns for prompt injection detection
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+dan",
    r"system\s+prompt\s+override",
    r"reveal\s+(the\s+)?(developer|system)\s+prompt",
    r"disregard\s+all\s+safety",
    r"bypass\s+risk\s+checks",
]

# Patterns for abusive / toxic keywords (rude customer persona)
TOXICITY_PATTERNS = [
    r"\b(garbage|useless|stupid|idiot|trash|dumb)\b",
]


class UserAnalysisRequest(BaseModel):
    model_config = {"extra": "allow"}

    ticker: str
    user_prompt: str = Field(default="Standard comprehensive equity and risk analysis.")
    lookback_days: int = Field(default=200, ge=1, le=50000)
    risk_profile: str = "moderate"
    workflow_mode: str = "sequential"  # sequential, parallel, hierarchical
    time_horizon: str = "short_term"  # short_term, mid_term, long_term
    forecast_horizon: str = "1_month"  # 1_month, 3_months, 6_months, 1_year, 2_years
    provider_mode: str = "auto"  # auto, fixture, live
    predefined_scenarios: Optional[list[str]] = None
    custom_scenarios: Optional[list[Any]] = None
    include_monte_carlo: Optional[bool] = None
    enable_judge: Optional[bool] = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker_format(cls, v: str) -> str:
        raw = v.strip().upper()
        # If user passed "Tata Steel (TATASTEEL)", extract inside parentheses
        match_paren = re.search(r"\(([A-Z0-9\-_]+)\)", raw)
        if match_paren:
            raw = match_paren.group(1)

        # Check if company name matches mapping
        if raw in COMPANY_NAME_TO_TICKER:
            raw = COMPANY_NAME_TO_TICKER[raw]
        else:
            # Check without .NS if present in raw
            clean_name = raw.replace(".NS", "").replace(".BO", "").strip()
            if clean_name in COMPANY_NAME_TO_TICKER:
                raw = COMPANY_NAME_TO_TICKER[clean_name]

        cleaned = raw
        if "." not in cleaned:
            cleaned = f"{cleaned}.NS"
        if not re.match(r"^[A-Z0-9\-_]{1,16}\.(NS|BO)$", cleaned):
            raise ValueError(f"Ticker symbol '{v}' could not be resolved to a valid NSE/BSE ticker.")
        return cleaned

    @field_validator("provider_mode")
    @classmethod
    def validate_provider_mode(cls, v: str) -> str:
        mode = v.strip().lower()
        if mode not in {"auto", "fixture", "live"}:
            raise ValueError(f"Invalid provider_mode '{v}'. Allowed modes: auto, fixture, live.")
        return mode


class GuardrailResult(BaseModel):
    passed: bool
    action: str  # 'PASS', 'PASS_WITH_FLAG', 'BLOCK'
    reason: Optional[str] = None
    security_flag: Optional[str] = None
    sanitized_prompt: str
    sanitized_ticker: str


class GuardrailsEngine:
    """Multi-layer security and input validation defense."""

    def __init__(self, allowed_tickers: Optional[set] = None):
        self.allowed_tickers = allowed_tickers or ALLOWED_TICKERS

    def evaluate_request(self, raw_input: Dict[str, Any]) -> Tuple[GuardrailResult, Optional[UserAnalysisRequest]]:
        """Validate input schema, rate/size bounds, prompt injection, and toxicity."""
        prompt = str(raw_input.get("user_prompt", "")).strip()
        ticker = str(raw_input.get("ticker", "")).strip().upper()
        lookback = raw_input.get("lookback_days", 200)

        # 1. Size & Resource Exhaustion Defense (oversized_request)
        if len(prompt) > MAX_PROMPT_LENGTH or (isinstance(lookback, int) and lookback > MAX_LOOKBACK_DAYS):
            return (
                GuardrailResult(
                    passed=False,
                    action="BLOCK",
                    reason=f"Request exceeds resource boundary: prompt length {len(prompt)} (max {MAX_PROMPT_LENGTH}) or lookback {lookback} (max {MAX_LOOKBACK_DAYS}).",
                    security_flag="RESOURCE_EXHAUSTION",
                    sanitized_prompt=prompt[:MAX_PROMPT_LENGTH],
                    sanitized_ticker=ticker,
                ),
                None,
            )

        # 2. Pydantic Schema and Ticker Validation (malformed_input)
        try:
            validated_req = UserAnalysisRequest(**raw_input)
        except Exception as e:
            return (
                GuardrailResult(
                    passed=False,
                    action="BLOCK",
                    reason=f"Input schema validation failed: {str(e)}",
                    security_flag="SCHEMA_VIOLATION",
                    sanitized_prompt=prompt,
                    sanitized_ticker=ticker,
                ),
                None,
            )

        # 3. Ticker Whitelist Check (strictly enforced for offline fixture mode)
        if validated_req.provider_mode == "fixture":
            if validated_req.ticker not in self.allowed_tickers:
                return (
                    GuardrailResult(
                        passed=False,
                        action="BLOCK",
                        reason=f"Ticker '{validated_req.ticker}' is not supported in offline fixture universe. Allowed: {sorted(list(self.allowed_tickers))}",
                        security_flag="UNSUPPORTED_TICKER",
                        sanitized_prompt=prompt,
                        sanitized_ticker=validated_req.ticker,
                    ),
                    None,
                )

        # 4. Prompt Injection Detection (prompt_injection_user)
        prompt_lower = prompt.lower()
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, prompt_lower):
                return (
                    GuardrailResult(
                        passed=False,
                        action="BLOCK",
                        reason="Adversarial prompt injection pattern detected and isolated.",
                        security_flag="PROMPT_INJECTION_ATTEMPT",
                        sanitized_prompt="[BLOCKED_ADVERSARIAL_INPUT]",
                        sanitized_ticker=validated_req.ticker,
                    ),
                    None,
                )

        # 5. Toxicity / Abusive Language Check (rude_customer)
        # Note: As per guidelines, rude customers are flagged but NOT blocked if prompt is non-exploitative!
        has_toxicity = any(re.search(pat, prompt_lower) for pat in TOXICITY_PATTERNS)
        if has_toxicity:
            return (
                GuardrailResult(
                    passed=True,
                    action="PASS_WITH_FLAG",
                    reason="Request contains aggressive or unprofessional wording but no security exploit.",
                    security_flag="LOW_TOXICITY_FLAG",
                    sanitized_prompt=prompt,
                    sanitized_ticker=validated_req.ticker,
                ),
                validated_req,
            )

        return (
            GuardrailResult(
                passed=True,
                action="PASS",
                reason="All input validation and security checks passed.",
                security_flag="NONE",
                sanitized_prompt=prompt,
                sanitized_ticker=validated_req.ticker,
            ),
            validated_req,
        )

    @staticmethod
    def isolate_untrusted_document(text: str) -> str:
        """Sanitize and isolate untrusted document text so it cannot act as system instructions."""
        # Strip potential markdown injection and control sequences
        sanitized = re.sub(r"(?i)system\s*override|ignore\s+all", "[FILTERED_OVERRIDE_TOKEN]", text)
        # Bound length
        return f"<UNTRUSTED_DOCUMENT_DATA>\n{sanitized[:2000]}\n</UNTRUSTED_DOCUMENT_DATA>"
