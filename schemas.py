from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# --- PART 1: DATABASE & METRICS ---

class ProjectMetrics(BaseModel):
    stars_24h: int = Field(..., description="Stars gained in the last 24 hours")
    stars_total: int = Field(..., description="Total star count")
    forks_24h: int = Field(default=0, description="Forks in last 24h")
    age_days: int = Field(..., description="Days since repository creation")
    last_commit_date: datetime = Field(..., description="Timestamp of the last push/commit")

class ProductionSignals(BaseModel):
    has_docker: bool = Field(default=False, description="True if Dockerfile/compose exists")
    has_ci: bool = Field(default=False, description="True if GitHub Actions/CircleCI exists")
    production_signals: int = Field(default=0, description="Count of 'serious' keywords (deploy, on-prem, etc.)")
    
    # These are placeholders that the AI will overwrite later
    category_guess: str = Field(default="pending", description="AI Classification")
    category_confidence: float = Field(default=0.0, description="AI Confidence Score")

class NormalizedProject(BaseModel):
    source: str = "github"
    title: str
    description: Optional[str]
    url: str
    metrics: ProjectMetrics
    signals: ProductionSignals
    raw_text: str = Field(..., description="Combined README + File Structure for context")

# --- PART 2: AI JUDGE OUTPUT (The Strict Rules) ---

class JudgeOutput(BaseModel):
    # 1. SCORING (0-10)
    novelty: int = Field(..., ge=0, le=10, description="0=Wrapper/Copy, 10=New Paradigm/Research")
    market_leverage: int = Field(..., ge=0, le=10, description="0=Niche/Toy, 10=Global Infra/B2B")
    moat_potential: int = Field(..., ge=0, le=10, description="0=Easy to copy, 10=Deep Tech/Hard")
    execution_signal: int = Field(..., ge=0, le=10, description="0=Spaghetti code, 10=Enterprise grade/Docs/Tests")
    time_to_market: int = Field(..., ge=0, le=10, description="0=Concept only, 10=Production Ready")
    
    # 2. CLASSIFICATION (Crucial for Client)
    category_guess: str = Field(..., description="Pick one: agents, infra, devtools, ops, evals, other")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")

    # 3. CONTENT & REASONING
    reject_flags: List[str] = Field(default_factory=list, description="List of red flags (e.g. 'no_code', 'wrapper', 'student_project')")
    one_line_reason: str = Field(..., description="One sentence explaining the decision")
    preview_post: str = Field(..., description="The final Russian Telegram post. REQUIRED.")