"""Financial Evidence and Ratio Calculator for MCP Tool 2."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RatioCalculationRequest(BaseModel):
    ticker: str
    total_debt: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    operating_income: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    reporting_period: str = "FY2024-2025"
    unit: str = "INR_CRORES"


class RatioCalculationResponse(BaseModel):
    ticker: str
    reporting_period: str
    unit: str
    calculated_ratios: Dict[str, float] = Field(default_factory=dict)
    missing_inputs: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quality_status: str  # valid, partial, invalid


class DocumentEvidenceRequest(BaseModel):
    ticker: str
    document_name: str
    query: str
    max_snippets: int = Field(default=3, ge=1, le=10)
    max_snippet_chars: int = Field(default=300, ge=50, le=1000)


class DocumentSnippetResponse(BaseModel):
    ticker: str
    document_name: str
    query: str
    snippets: List[Dict[str, Any]] = Field(default_factory=list)
    warning: Optional[str] = None


class FinancialEvidenceCalculator:
    def __init__(self, docs_dir: Optional[Path] = None):
        self.docs_dir = docs_dir or Path("data/reports")

    def calculate_ratios(self, req: RatioCalculationRequest) -> RatioCalculationResponse:
        ratios: Dict[str, float] = {}
        missing: List[str] = []
        warnings: List[str] = []

        # 1. Debt to Equity
        if req.total_debt is not None and req.total_equity is not None:
            if req.total_equity == 0:
                warnings.append("Zero equity: Debt-to-Equity undefined")
            elif req.total_equity < 0:
                warnings.append("Negative equity detected")
                ratios["debt_to_equity"] = round(req.total_debt / req.total_equity, 4)
            else:
                ratios["debt_to_equity"] = round(req.total_debt / req.total_equity, 4)
        else:
            missing.append("total_debt or total_equity")

        # 2. Current Ratio
        if req.current_assets is not None and req.current_liabilities is not None:
            if req.current_liabilities <= 0:
                warnings.append("Invalid current liabilities (<=0)")
            else:
                ratios["current_ratio"] = round(req.current_assets / req.current_liabilities, 4)
        else:
            missing.append("current_assets or current_liabilities")

        # 3. Operating Margin
        if req.operating_income is not None and req.revenue is not None:
            if req.revenue <= 0:
                warnings.append("Invalid revenue (<=0)")
            else:
                ratios["operating_margin"] = round(req.operating_income / req.revenue, 4)
        else:
            missing.append("operating_income or revenue")

        # 4. Return on Equity (ROE)
        if req.net_income is not None and req.total_equity is not None:
            if req.total_equity > 0:
                ratios["roe"] = round(req.net_income / req.total_equity, 4)
            else:
                warnings.append("Cannot compute ROE with non-positive equity")
        else:
            missing.append("net_income or total_equity")

        quality = "valid" if ratios and not missing else ("partial" if ratios else "invalid")
        return RatioCalculationResponse(
            ticker=req.ticker.upper(),
            reporting_period=req.reporting_period,
            unit=req.unit,
            calculated_ratios=ratios,
            missing_inputs=missing,
            warnings=warnings,
            quality_status=quality,
        )

    def extract_bounded_evidence(self, req: DocumentEvidenceRequest) -> DocumentSnippetResponse:
        """Extract bounded snippets with explicit page references from local filing repository."""
        doc_path = self.docs_dir / req.document_name
        if not doc_path.exists():
            return DocumentSnippetResponse(
                ticker=req.ticker.upper(),
                document_name=req.document_name,
                query=req.query,
                snippets=[],
                warning=f"Document '{req.document_name}' not found in {self.docs_dir}",
            )

        snippets = []
        try:
            # Supports text files or text-formatted report extracts
            with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Split by explicit page markers if present (e.g. --- Page X ---)
            pages = content.split("--- Page ")
            q_lower = req.query.lower()

            for page_block in pages:
                if not page_block.strip():
                    continue
                # Determine page number
                lines = page_block.splitlines()
                page_header = lines[0].strip()
                page_num = 1
                try:
                    page_num = int(page_header.split("---")[0].strip())
                except ValueError:
                    pass

                text_body = "\n".join(lines[1:]) if len(lines) > 1 else page_block
                if q_lower in text_body.lower():
                    # Extract bounded snippet around query match
                    idx = text_body.lower().find(q_lower)
                    start_char = max(0, idx - 50)
                    end_char = min(len(text_body), idx + req.max_snippet_chars)
                    snippet_text = text_body[start_char:end_char].replace("\n", " ").strip()
                    snippets.append(
                        {
                            "document_name": req.document_name,
                            "page_number": page_num,
                            "text_snippet": f"...{snippet_text}...",
                            "match_length": len(snippet_text),
                        }
                    )
                    if len(snippets) >= req.max_snippets:
                        break

            return DocumentSnippetResponse(
                ticker=req.ticker.upper(),
                document_name=req.document_name,
                query=req.query,
                snippets=snippets,
                warning=None if snippets else f"No mentions of '{req.query}' found in document.",
            )
        except Exception as e:
            return DocumentSnippetResponse(
                ticker=req.ticker.upper(),
                document_name=req.document_name,
                query=req.query,
                snippets=[],
                warning=f"Error reading document: {str(e)}",
            )
