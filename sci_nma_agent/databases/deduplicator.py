"""
Multi-Tier Bibliographic Deduplication Engine with Provenance Retention.
Eliminates duplicates while preserving multi-database identities and citation provenance.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple
from .corpus_repository import CanonicalRecord


class ProvenanceDeduplicator:
    """
    Executes hierarchical deduplication:
      Level 1: Exact DOI matching
      Level 2: Exact PubMed ID matching
      Level 3: Normalized Title + Publication Year + First Author similarity
    
    Preserves all database source tags and native accession numbers upon merging.
    """

    @staticmethod
    def normalize_title(title: str) -> str:
        if not title:
            return ""
        # Remove HTML tags, punctuation, and normalize whitespace
        t = re.sub(r"<[^>]+>", "", title)
        t = re.sub(r"[^\w\s]", "", t).lower()
        return " ".join(t.split())

    @staticmethod
    def title_similarity(t1: str, t2: str) -> float:
        if not t1 or not t2:
            return 0.0
        return SequenceMatcher(None, t1, t2).ratio()

    @classmethod
    def merge_records(cls, base: CanonicalRecord, incoming: CanonicalRecord, merge_reason: str) -> CanonicalRecord:
        """Merge incoming duplicate record into base record, preserving all identities."""
        # 1. Merge sources
        for s in incoming.sources:
            if s not in base.sources:
                base.sources.append(s)
        base.sources.sort()

        # 2. Merge db_ids
        for k, v in incoming.db_ids.items():
            if v and not base.db_ids.get(k):
                base.db_ids[k] = v

        # 3. Fill missing DOI
        if not base.doi and incoming.doi:
            base.doi = incoming.doi

        # 4. Fill missing / longer abstract
        if len(incoming.abstract) > len(base.abstract):
            base.abstract = incoming.abstract

        # 5. Fill missing year
        if not base.year and incoming.year:
            base.year = incoming.year

        # 6. Fill missing journal
        if not base.journal and incoming.journal:
            base.journal = incoming.journal

        # 7. Merge keywords
        for kw in incoming.keywords:
            if kw not in base.keywords:
                base.keywords.append(kw)

        # 8. Merge authors if base is empty
        if not base.authors and incoming.authors:
            base.authors = list(incoming.authors)

        return base

    @classmethod
    def deduplicate(cls, records: List[CanonicalRecord]) -> Tuple[List[CanonicalRecord], Dict[str, Any], List[Dict[str, Any]]]:
        """
        Deduplicate record list while retaining complete database provenance.
        Returns:
          (unique_records, metrics_dict, duplicate_audit_log)
        """
        unique_list: List[CanonicalRecord] = []
        doi_map: Dict[str, CanonicalRecord] = {}
        pmid_map: Dict[str, CanonicalRecord] = {}
        audit_log: List[Dict[str, Any]] = []

        for rec in records:
            matched_base = None
            reason = ""

            # --- Level 1: DOI Match ---
            if rec.doi and rec.doi in doi_map:
                matched_base = doi_map[rec.doi]
                reason = f"Level 1 Exact DOI match: {rec.doi}"

            # --- Level 2: PMID Match ---
            elif rec.db_ids.get("pubmed_pmid") and rec.db_ids["pubmed_pmid"] in pmid_map:
                matched_base = pmid_map[rec.db_ids["pubmed_pmid"]]
                reason = f"Level 2 Exact PMID match: {rec.db_ids['pubmed_pmid']}"

            # --- Level 3: Normalized Title + Year / Author Match ---
            if not matched_base and rec.title:
                norm_rec_title = cls.normalize_title(rec.title)
                if len(norm_rec_title) >= 15:  # Only for substantive titles
                    for existing in unique_list:
                        norm_exist_title = cls.normalize_title(existing.title)
                        sim = cls.title_similarity(norm_rec_title, norm_exist_title)

                        # High similarity (>92%) with matching/compatible year
                        if sim >= 0.92:
                            years_compatible = (
                                rec.year is None or
                                existing.year is None or
                                abs(rec.year - existing.year) <= 1
                            )
                            if years_compatible:
                                matched_base = existing
                                reason = f"Level 3 Title similarity ({sim:.1%}) with year compatibility"
                                break

            # If duplicate detected, merge into existing
            if matched_base:
                cls.merge_records(matched_base, rec, reason)
                # Re-index maps in case newly merged fields provide more keys
                if matched_base.doi:
                    doi_map[matched_base.doi] = matched_base
                if matched_base.db_ids.get("pubmed_pmid"):
                    pmid_map[matched_base.db_ids["pubmed_pmid"]] = matched_base

                audit_log.append({
                    "duplicate_master_id": rec.master_id,
                    "merged_into_master_id": matched_base.master_id,
                    "reason": reason,
                    "title": rec.title,
                    "sources": rec.sources
                })
            else:
                # Add as unique
                unique_list.append(rec)
                if rec.doi:
                    doi_map[rec.doi] = rec
                if rec.db_ids.get("pubmed_pmid"):
                    pmid_map[rec.db_ids["pubmed_pmid"]] = rec

        # Assign clean incremental master IDs
        for i, u_rec in enumerate(unique_list, start=1):
            u_rec.master_id = f"REC-{i:05d}"

        total_raw = len(records)
        unique_count = len(unique_list)
        duplicates_removed = total_raw - unique_count

        metrics = {
            "total_raw_records": total_raw,
            "unique_records": unique_count,
            "duplicates_removed": duplicates_removed
        }

        return unique_list, metrics, audit_log
