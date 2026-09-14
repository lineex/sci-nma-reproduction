"""
sci_nma_agent
=============
Top-Tier Medical Review & NMA Autonomous Agent: Publication-grade systematic reviews,
meta-analyses, and narrative review reproduction framework.
"""

__version__ = "1.1.0"
__author__ = "lineex"

from .core.audit_runner import AuditRunner, VerificationReport
from .core.gate1_search_flow import Gate1SearchFlow
from .core.gate2_evidence_provenance import Gate2EvidenceProvenance
from .core.gate3_statistics import Gate3Statistics
from .core.gate4_figure_vector import Gate4FigureVector
from .core.gate5_office_audit import Gate5OfficeAudit

from .databases.session_manager import BrowserSessionManager, InstitutionalSessionStatus
from .databases.corpus_repository import CanonicalRecord, FormatParsers, CorpusRepository
from .databases.deduplicator import ProvenanceDeduplicator
from .databases.audit_ledger import SearchAuditLedger
from .databases.screening_ledger import ScreeningLedger

__all__ = [
    "AuditRunner",
    "VerificationReport",
    "Gate1SearchFlow",
    "Gate2EvidenceProvenance",
    "Gate3Statistics",
    "Gate4FigureVector",
    "Gate5OfficeAudit",
    "BrowserSessionManager",
    "InstitutionalSessionStatus",
    "CanonicalRecord",
    "FormatParsers",
    "CorpusRepository",
    "ProvenanceDeduplicator",
    "SearchAuditLedger",
    "ScreeningLedger",
]
