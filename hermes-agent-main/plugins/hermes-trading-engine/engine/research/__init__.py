"""Phase 5: controlled Grok 4.3 research / probability engine.

Grok is research-only: it estimates probability and supplies evidence. It cannot
execute, size, or bypass the RiskEngine. Strategy code may consume calibrated
estimates, but every order still flows through RiskEngine + OMS.
"""

from __future__ import annotations

from .ambiguity import AmbiguityScorer
from .budget import ResearchBudget
from .calibration_adapter import CalibrationAdapter
from .ensemble import ForecastEnsemble
from .evidence_store import EvidenceStore
from .grok_client import GrokResearchClient
from .market_rules import MarketRuleParser
from .news_providers import (
    FixtureProvider,
    LiveReadOnlyProvider,
    NewsProvider,
    OfflineCacheProvider,
    get_provider,
    safe_market_context,
)
from .news_ranker import build_packet, contains_injection, news_adjustment, sanitize_snippet
from .news_scanner import NewsEvidenceScanner
from .news_schemas import NewsEvidenceItem, NewsPacket, NewsScanResult
from .probability import ProbabilityEstimator, evidence_score_of
from .replay_cache import ReplayResearchCache
from .schemas import (
    ONLINE_MODES,
    EvidenceItem,
    GrokProbabilityOutput,
    MarketRuleSummary,
    ProbabilityEstimateBundle,
    ResearchFailure,
)
from .source_cache import SourceCache
from .validators import (
    forbidden_execution_keys,
    redact,
    validate_probability_output,
)

__all__ = [
    "AmbiguityScorer", "ResearchBudget", "CalibrationAdapter", "ForecastEnsemble",
    "EvidenceStore", "GrokResearchClient", "MarketRuleParser", "ProbabilityEstimator",
    "evidence_score_of", "ReplayResearchCache", "SourceCache", "ONLINE_MODES",
    "EvidenceItem", "GrokProbabilityOutput", "MarketRuleSummary",
    "ProbabilityEstimateBundle", "ResearchFailure", "forbidden_execution_keys",
    "redact", "validate_probability_output",
    "NewsProvider", "OfflineCacheProvider", "FixtureProvider", "LiveReadOnlyProvider",
    "get_provider", "safe_market_context", "NewsEvidenceScanner", "NewsEvidenceItem",
    "NewsPacket", "NewsScanResult", "build_packet", "news_adjustment",
    "contains_injection", "sanitize_snippet",
]
