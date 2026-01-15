from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

# --- PART 1: NESTED DATA MODELS (Client Section 7) ---

class ProjectMetrics(BaseModel):
    """Hard numbers for filtering."""
    stars_24h: int = Field(default=0, description="Stars gained in last 24h")
    stars_total: int = Field(..., description="Total star count")
    forks_24h: int = Field(default=0, description="Forks in last 24h")
    age_days: int = Field(..., description="Days since creation")
    last_commit_date: datetime = Field(..., description="Timestamp of the last commit/push")

class ProductionSignals(BaseModel):
    """Boolean flags for 'Serious' engineering."""
    has_docker: bool = Field(default=False, description="Dockerfile or docker-compose found")
    has_ci: bool = Field(default=False, description="GitHub Actions/.circleci found")
    production_signals_count: int = Field(default=0, description="Total count of true signals (docker, ci, deploy keywords)")
    category_guess: str = Field(default="other", description="agents / infra / devtools / ops / evals")
    category_confidence: float = Field(default=0.0, description="Confidence score 0-1")

# --- PART 2: THE INPUT SCHEMA (Adapter Output) ---

class NormalizedProject(BaseModel):
    """
    The strict format required by Client Section 7.
    """
    source: str = "github"
    id: str = Field(..., description="Unique ID (e.g. github URL)")
    title: str
    description: Optional[str] = None
    url: HttpUrl
    
    # Nested Objects
    metrics: ProjectMetrics
    signals: ProductionSignals
    
    # Raw Content for AI
    raw_text: str = Field(..., description="Combined Readme + File Structure for LLM analysis")
    
    # Helper metadata (Internal use only, not for final JSON)
    created_at: datetime

# --- PART 3: THE OUTPUT SCHEMA (Judge Agent - Client Section 8) ---

class DecisionEnum(str, Enum):
    PUBLISH = "PUBLISH"
    REJECT = "REJECT"

class JudgeOutput(BaseModel):
    """
    The 5-point VC Scorecard.
    Scores must be 0-10.
    """
    # The 5 Criteria
    novelty: int = Field(..., ge=0, le=10, description="Is this new? (0-10)")
    market_leverage: int = Field(..., ge=0, le=10, description="Is the market huge? (0-10)")
    moat_potential: int = Field(..., ge=0, le=10, description="Is it hard to copy? (0-10)")
    execution_signal: int = Field(..., ge=0, le=10, description="Is the engineering elite? (0-10)")
    time_to_market: int = Field(..., ge=0, le=10, description="Is it ready now? (0-10)")

    category_guess: str = Field(..., description="Classify into: agents, infra, devtools, ops, evals, or other")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="How sure are you? (0.0 to 1.0)")
    
    # Flags & Reasoning
    reject_flags: List[str] = Field(default_factory=list, description="Tags like 'wrapper', 'no_user', 'toy_project'")
    one_line_reason: str = Field(..., description="Concise explanation for the decision")
    
    # Final Output
    final_decision: DecisionEnum
    preview_post: str = Field(..., description="Write a draft Telegram post for this project. REQUIRED even if rejected.")