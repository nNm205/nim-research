"""Agent layer — long-running pipelines that orchestrate tools + LLM calls.

Each agent owns one entity-level workflow:
  - ResearchAgent           → ResearchSession (search + save)
  - AnalysisAgent           → DocumentAnalysis (per-document deep insight)
  - SynthesisAgent          → Report (cross-document narrative + summary)
  - QualityAssuranceAgent   → Report (format / citation / fact / grammar)

Agents NEVER hold long-running references to a request session. The
service layer dispatches each run inside a fresh ``AsyncSessionLocal``.
"""

from app.agents.analysis_agent import AnalysisAgent
from app.agents.qa_agent import QualityAssuranceAgent
from app.agents.research_agent import ResearchAgent
from app.agents.synthesis_agent import SynthesisAgent

__all__ = [
    "AnalysisAgent",
    "QualityAssuranceAgent",
    "ResearchAgent",
    "SynthesisAgent",
]
