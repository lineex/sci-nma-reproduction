"""
sci_nma_agent.databases
=======================
Multi-database query formulation, institutional session management,
full-corpus ingestion without relevance truncation, provenance-retaining deduplication,
search audit tables, and two-stage screening ledgers.
"""

from .query_harmonizer import QueryHarmonizer
from .pubmed import PubMedQueryBuilder
from .embase import EmbaseQueryBuilder
from .cochrane import CochraneQueryBuilder
from .wos import WoSQueryBuilder
from .scopus import ScopusQueryBuilder

from .session_manager import BrowserSessionManager, InstitutionalSessionStatus
from .corpus_repository import CanonicalRecord, FormatParsers, CorpusRepository
from .deduplicator import ProvenanceDeduplicator
from .audit_ledger import SearchAuditLedger
from .screening_ledger import ScreeningLedger

__all__ = [
    "QueryHarmonizer",
    "PubMedQueryBuilder",
    "EmbaseQueryBuilder",
    "CochraneQueryBuilder",
    "WoSQueryBuilder",
    "ScopusQueryBuilder",
    "BrowserSessionManager",
    "InstitutionalSessionStatus",
    "CanonicalRecord",
    "FormatParsers",
    "CorpusRepository",
    "ProvenanceDeduplicator",
    "SearchAuditLedger",
    "ScreeningLedger",
]
