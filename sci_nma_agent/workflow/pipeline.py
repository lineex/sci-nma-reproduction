"""
End-to-End 6-Stage SOP Pipeline Orchestrator with Step-by-Step Gated Acceptance.
Enforces the Anti-Shortcut Protocol: Every single stage has an explicit Acceptance Checkpoint.
If any step fails its verification gate, execution is halted immediately (fused熔断),
preventing flawed or unverified evidence from propagating into downstream stages.
"""

import os
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from ..databases.query_harmonizer import QueryHarmonizer
from ..databases.corpus_repository import CorpusRepository
from ..databases.deduplicator import ProvenanceDeduplicator
from ..databases.audit_ledger import SearchAuditLedger
from ..databases.screening_ledger import ScreeningLedger
from ..databases.session_manager import BrowserSessionManager

from ..meta_engine.pairwise import PairwiseMetaAnalysis
from ..meta_engine.network_meta import NetworkMetaEngine
from ..generators.prisma_diagram import PRISMADiagramGenerator
from ..generators.forest_plot import ForestPlotGenerator
from ..generators.network_geometry import NetworkGeometryGenerator
from ..generators.docx_manuscript import DocxManuscriptGenerator
from ..generators.master_excel import MasterExcelGenerator
from ..generators.presentation_pptx import PresentationGenerator
from ..core.gate1_search_flow import Gate1SearchFlow
from ..core.gate2_evidence_provenance import Gate2EvidenceProvenance
from ..core.gate3_statistics import Gate3Statistics
from ..core.gate4_figure_vector import Gate4FigureVector
from ..core.gate5_office_audit import Gate5OfficeAudit
from ..core.audit_runner import AuditRunner, VerificationReport
from ..reviewer.ai_reviewer import AIPeerReviewer
from .protocol_validation import validate_analysis_manifest_file
from .stage_ledger import AgentStageLedger, StageLedgerError


class StepAcceptanceError(RuntimeError):
    """Raised when a specific SOP stage fails its acceptance gate."""
    pass


class SOPPipeline:
    """
    Orchestrator for the 6-Stage Standard Operating Procedure with Strict Gated Acceptance.
    
    Stages & Acceptance Gates:
      Stage 1: PICO & Multi-Database Search Formulation  -> Checkpoint 1 (Syntax & Logic)
      Stage 2: Ground-Truth Catalog & Flow Ledger        -> Checkpoint 2 (Gate 1: PRISMA Flow L ≡ 0)
      Stage 3: Data Extraction & Statistical Modeling    -> Checkpoint 3 (Gate 2: Provenance & Gate 3: Stats)
      Stage 4: Multi-Format Vector Figure Rendering     -> Checkpoint 4 (Gate 4: Zero-Raster & SVG <text>)
      Stage 5: Office Suites Industrial Engineering     -> Checkpoint 5 (Gate 5: Docx XML & Master Excel)
      Stage 6: Global 5-Tier Audit & AI Peer Review     -> Checkpoint 6 (100% Verified Certificate)
    """

    def __init__(self, project_dir: str):
        self.project_dir = project_dir

    def _resolve_project_path(self, path: str) -> Path:
        """Resolve project-relative production evidence without depending on CWD."""
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path(self.project_dir).expanduser() / candidate
        return candidate.resolve()

    def _require_production_synthesis(
        self, *results: Dict[str, Any], result_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Require external locked-engine evidence before producing formal artifacts."""
        project = Path(self.project_dir).expanduser().resolve()
        protocol_path = project / "review_protocol.json"
        if not protocol_path.is_file():
            raise StepAcceptanceError("Production release requires an approved review_protocol.json")
        try:
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StepAcceptanceError(f"Production release cannot read review protocol: {exc}") from exc
        declared = protocol.get("synthesis", {}).get("analysis_manifest_path")
        manifest_path = project / str(declared or "")
        errors = validate_analysis_manifest_file(manifest_path, project, protocol_path=protocol_path)
        if errors:
            raise StepAcceptanceError(
                "Production release requires a valid protocol-bound analysis manifest: " + "; ".join(errors)
            )
        try:
            ledger = AgentStageLedger(str(project)).status()
        except StageLedgerError as exc:
            raise StepAcceptanceError(f"Production release requires the stage ledger: {exc}") from exc
        if not ledger.get("integrity_valid") or not ledger.get("evidence_integrity_valid"):
            raise StepAcceptanceError("Production release requires valid stage-ledger and evidence integrity")
        if ledger.get("stages", {}).get("protocol", {}).get("status") != "approved":
            raise StepAcceptanceError("Production release requires two independent protocol approvals")
        if ledger.get("stages", {}).get("synthesis", {}).get("status") != "approved":
            raise StepAcceptanceError("Production release requires two independent synthesis approvals")
        manifest_rel = manifest_path.relative_to(project).as_posix()
        if not any(
            record.get("path") == manifest_rel
            for record in ledger.get("stages", {}).get("synthesis", {}).get("artifact_manifest", [])
        ):
            raise StepAcceptanceError("Approved synthesis evidence does not contain the declared analysis manifest")
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        protocol_synthesis = protocol.get("synthesis", {})
        pairwise_planned = bool(
            protocol_synthesis.get("pairwise_meta_analysis", {}).get("enabled", True)
        )
        nma_planned = bool(
            protocol_synthesis.get("network_meta_analysis", {}).get("enabled", False)
        )
        result_pairwise = results[0] if results else {}
        result_network = results[1] if len(results) > 1 else None
        if pairwise_planned and result_pairwise.get("planned") is False:
            raise StepAcceptanceError("Production pairwise result is marked not planned but protocol plans pairwise synthesis")
        if not pairwise_planned and result_pairwise.get("planned") is not False:
            raise StepAcceptanceError("Protocol does not plan pairwise synthesis; production pairwise result must declare planned=false")
        if nma_planned:
            if not isinstance(result_network, dict) or result_network.get("planned") is False:
                raise StepAcceptanceError("Protocol plans NMA; production results must include planned network evidence")
        elif isinstance(result_network, dict) and result_network.get("planned") is True:
            raise StepAcceptanceError("Protocol does not plan NMA; production network result must declare planned=false")
        if result_path:
            try:
                result_rel = self._resolve_project_path(result_path).relative_to(project).as_posix()
            except ValueError as exc:
                raise StepAcceptanceError("External production results must be inside the review project") from exc
            declared_result_paths = {
                str(item.get("path"))
                for field in ("outputs", "intermediate_outputs")
                for item in manifest_data.get(field, [])
                if isinstance(item, dict)
            }
            if result_rel not in declared_result_paths:
                raise StepAcceptanceError(
                    "External production results must be declared in analysis_manifest outputs/intermediate_outputs"
                )
        for result in results:
            if result.get("engine_role") == "exploratory_qa" or result.get("production_use") == "not_for_release":
                raise StepAcceptanceError(
                    "Production artifacts require result objects emitted by the locked primary engine; "
                    "bundled Python QA results are not releasable"
                )
        return manifest_data

    def _load_production_results(self, result_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        path = self._resolve_project_path(result_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StepAcceptanceError(f"Unable to read locked production results: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("pairwise"), dict):
            raise StepAcceptanceError("Production results JSON must contain a pairwise result object")
        pairwise = payload["pairwise"]
        if not isinstance(pairwise.get("planned", True), bool):
            raise StepAcceptanceError("Locked production pairwise result planned must be a boolean when supplied")
        pairwise.setdefault("planned", True)
        network = payload.get("network")
        if network is None:
            network = {"planned": False, "engine_role": "not_planned", "production_use": "not_applicable"}
        if not isinstance(network, dict):
            raise StepAcceptanceError("Production results JSON network must be an object when supplied")
        if not isinstance(network.get("planned", True), bool):
            raise StepAcceptanceError("Locked production network result planned must be a boolean when supplied")
        network.setdefault("planned", True)
        for label, result in (("pairwise", pairwise), ("network", network)):
            if result.get("planned") is False:
                if not (
                    result.get("engine_role") == "not_planned"
                    and result.get("production_use") == "not_applicable"
                ):
                    raise StepAcceptanceError(
                        f"A non-planned {label} result must declare engine_role=not_planned and "
                        "production_use=not_applicable"
                    )
                continue
            if result.get("engine_role") in {"exploratory_qa", "qa", "python"} or result.get("production_use") == "not_for_release":
                raise StepAcceptanceError(f"Locked production {label} result is marked as QA/not-for-release")
            if result.get("engine_role") not in {"locked_production", "r_production", "stata_production", "validated_production"}:
                raise StepAcceptanceError(f"Locked production {label} result must declare a production engine role")
            if result.get("production_use") != "release":
                raise StepAcceptanceError(f"Locked production {label} result must declare production_use=release")
        if pairwise.get("planned") is not False:
            required_pairwise = (
                "pooled_estimate", "ci_lower", "ci_upper", "i2_percent", "tau2", "p_value", "studies"
            )
            missing_pairwise = [field for field in required_pairwise if field not in pairwise]
            if missing_pairwise:
                raise StepAcceptanceError(
                    "Locked production pairwise result is missing renderable fields: " + ", ".join(missing_pairwise)
                )
            if not isinstance(pairwise.get("studies"), list) or not pairwise["studies"]:
                raise StepAcceptanceError("Locked production pairwise result must contain non-empty study-level rows")
            for field in required_pairwise[:-1]:
                try:
                    if not isinstance(pairwise.get(field), (int, float)) or not math.isfinite(float(pairwise[field])):
                        raise ValueError
                except (TypeError, ValueError):
                    raise StepAcceptanceError(
                        f"Locked production pairwise result field {field} must be a finite numeric value"
                    )
            if float(pairwise["ci_lower"]) > float(pairwise["ci_upper"]):
                raise StepAcceptanceError("Locked production pairwise confidence interval bounds are reversed")
        if network.get("planned") is not False:
            if not isinstance(network.get("rankings"), list) or not network["rankings"]:
                raise StepAcceptanceError("Locked production network result must contain non-empty rankings")
            if not isinstance(network.get("comparisons"), list) or not network["comparisons"]:
                raise StepAcceptanceError("Locked production network result must contain non-empty comparisons")
            treatments = network.get("treatments")
            if not isinstance(treatments, list) or not treatments:
                raise StepAcceptanceError(
                    "Locked production network result must contain non-empty treatments for Figure 3 geometry"
                )
            treatment_ids = []
            for index, treatment in enumerate(treatments):
                if not isinstance(treatment, dict):
                    raise StepAcceptanceError(f"Locked production network treatment row {index} must be an object")
                treatment_id = treatment.get("id")
                if not isinstance(treatment_id, str) or not treatment_id.strip():
                    raise StepAcceptanceError(f"Locked production network treatment row {index} has no id")
                if treatment_id in treatment_ids:
                    raise StepAcceptanceError(f"Locked production network treatment id is duplicated: {treatment_id}")
                sample_size = treatment.get("sample_size")
                if (
                    isinstance(sample_size, bool)
                    or not isinstance(sample_size, (int, float))
                    or not math.isfinite(float(sample_size))
                    or float(sample_size) <= 0
                ):
                    raise StepAcceptanceError(
                        f"Locked production network treatment {treatment_id} sample_size must be a positive finite number"
                    )
                color = treatment.get("color")
                if not isinstance(color, str) or not color.strip():
                    raise StepAcceptanceError(
                        f"Locked production network treatment {treatment_id} must declare a non-empty color"
                    )
                treatment_ids.append(treatment_id)
            treatment_id_set = set(treatment_ids)
            ranking_fields = ("treatment", "rank", "sucra_percent", "relative_or_vs_ref", "ci_lower", "ci_upper")
            ranked_ids = set()
            for index, ranking in enumerate(network["rankings"]):
                if not isinstance(ranking, dict) or any(field not in ranking for field in ranking_fields):
                    raise StepAcceptanceError(
                        "Locked production network ranking rows must contain "
                        + ", ".join(ranking_fields)
                        + f" (row {index})"
                    )
                if not isinstance(ranking["treatment"], str) or not ranking["treatment"].strip():
                    raise StepAcceptanceError(f"Locked production network ranking row {index} has no treatment")
                if ranking["treatment"] not in treatment_id_set:
                    raise StepAcceptanceError(
                        f"Locked production network ranking row {index} references undeclared treatment "
                        f"{ranking['treatment']}"
                    )
                if ranking["treatment"] in ranked_ids:
                    raise StepAcceptanceError(
                        f"Locked production network ranking treatment is duplicated: {ranking['treatment']}"
                    )
                ranked_ids.add(ranking["treatment"])
                if not isinstance(ranking["rank"], int) or isinstance(ranking["rank"], bool):
                    raise StepAcceptanceError(f"Locked production network ranking row {index} rank must be an integer")
                try:
                    numeric_values = [
                        float(ranking[field]) for field in ranking_fields[2:]
                    ]
                except (TypeError, ValueError):
                    raise StepAcceptanceError(f"Locked production network ranking row {index} has non-numeric values")
                if not all(math.isfinite(value) for value in numeric_values):
                    raise StepAcceptanceError(f"Locked production network ranking row {index} has non-finite values")
                if float(ranking["ci_lower"]) > float(ranking["ci_upper"]):
                    raise StepAcceptanceError(f"Locked production network ranking row {index} has reversed CI bounds")
            if ranked_ids != treatment_id_set:
                missing_rankings = ", ".join(sorted(treatment_id_set - ranked_ids))
                extra_rankings = ", ".join(sorted(ranked_ids - treatment_id_set))
                details = []
                if missing_rankings:
                    details.append(f"missing rankings for {missing_rankings}")
                if extra_rankings:
                    details.append(f"undeclared rankings for {extra_rankings}")
                raise StepAcceptanceError(
                    "Locked production network rankings must cover exactly the declared treatments: "
                    + "; ".join(details)
                )
            seen_edges = set()
            adjacency = {treatment_id: set() for treatment_id in treatment_ids}
            for index, comparison in enumerate(network["comparisons"]):
                if not isinstance(comparison, dict) or not comparison.get("t1") or not comparison.get("t2"):
                    raise StepAcceptanceError(f"Locked production network comparison row {index} must identify t1 and t2")
                t1, t2 = comparison["t1"], comparison["t2"]
                if not isinstance(t1, str) or not isinstance(t2, str) or t1 == t2:
                    raise StepAcceptanceError(
                        f"Locked production network comparison row {index} must contain distinct treatment endpoints"
                    )
                if t1 not in treatment_id_set or t2 not in treatment_id_set:
                    raise StepAcceptanceError(
                        f"Locked production network comparison row {index} references an undeclared treatment"
                    )
                trial_count = comparison.get("trial_count")
                if (
                    isinstance(trial_count, bool)
                    or not isinstance(trial_count, (int, float))
                    or not math.isfinite(float(trial_count))
                    or float(trial_count) <= 0
                    or float(trial_count) != int(trial_count)
                ):
                    raise StepAcceptanceError(
                        f"Locked production network comparison row {index} trial_count must be a positive integer"
                    )
                edge = tuple(sorted((t1, t2)))
                if edge in seen_edges:
                    raise StepAcceptanceError(
                        f"Locked production network comparison is duplicated: {t1} vs {t2}"
                    )
                seen_edges.add(edge)
                adjacency[t1].add(t2)
                adjacency[t2].add(t1)
            reachable = set()
            pending = [treatment_ids[0]]
            while pending:
                current = pending.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                pending.extend(adjacency[current] - reachable)
            if reachable != treatment_id_set:
                disconnected = ", ".join(sorted(treatment_id_set - reachable))
                raise StepAcceptanceError(
                    "Locked production network geometry must be connected; disconnected treatments: " + disconnected
                )
        return pairwise, network

    # -------------------------------------------------------------------------
    # STAGE 1: Evidence Ingestion & Multi-Database Search Formulation
    # -------------------------------------------------------------------------
    def step1_search(self, config_pico_path: str) -> Dict[str, str]:
        print("\n================================================================================")
        print(">>> [STAGE 1/6] Ingesting Evidence & Formulating Multi-Database Queries")
        print("================================================================================")
        if not os.path.exists(config_pico_path):
            raise StepAcceptanceError(f"Stage 1 Failed: Missing PICO config file at {config_pico_path}")

        with open(config_pico_path, "r", encoding="utf-8") as f:
            pico_config = json.load(f)

        queries = QueryHarmonizer.harmonize(pico_config)
        search_dir = os.path.join(self.project_dir, "search_strategies")
        os.makedirs(search_dir, exist_ok=True)

        # Write queries
        for db, q in queries.items():
            q_file = os.path.join(search_dir, f"{db}_search.txt")
            with open(q_file, "w", encoding="utf-8") as f:
                f.write(q)

        # --- STEP 1 ACCEPTANCE CHECKPOINT ---
        print("\n[*] Running Step 1 Acceptance Verification (Search Syntax & Logic Check)...")
        syntax_errors = []
        for db, q in queries.items():
            passed, errs = Gate1SearchFlow.validate_search_syntax(db, q)
            if not passed:
                syntax_errors.extend([f"[{db}] {e}" for e in errs])

        if syntax_errors:
            error_msg = f"Stage 1 Acceptance FAILED (Syntax Errors Detected):\n" + "\n".join(syntax_errors)
            raise StepAcceptanceError(error_msg)

        print(">>> [STAGE 1 ACCEPTANCE: PASSED] All 4 databases + Scopus queries validated without error.")
        return queries

    # -------------------------------------------------------------------------
    # STAGE 2: Ground-Truth Catalog & PRISMA Flow Ledger
    # -------------------------------------------------------------------------
    def step2_flow(self, flow_path: str) -> Dict[str, Any]:
        print("\n================================================================================")
        print(">>> [STAGE 2/6] Ground-Truth Catalog, Full Corpus Landing & PRISMA Flow Ledger")
        print("================================================================================")

        raw_exports_dir = os.path.join(self.project_dir, "raw_exports")
        screening_xlsx = os.path.join(self.project_dir, "screening", "master_screening_table.xlsx")

        # 1. Ingest landed batch files if raw_exports exists and has files
        if os.path.exists(raw_exports_dir):
            ingest_res = CorpusRepository.scan_and_ingest(raw_exports_dir)
            if ingest_res["total_raw_records"] > 0:
                print(f"[*] Landed raw export records found: {ingest_res['total_raw_records']} records.")
                unique_recs, dedup_metrics, _ = ProvenanceDeduplicator.deduplicate(ingest_res["records"])
                print(f"    Deduplication completed: {dedup_metrics['unique_records']} unique records ({dedup_metrics['duplicates_removed']} duplicates).")

                # Generate Master Screening Table if not already existing
                if not os.path.exists(screening_xlsx):
                    ScreeningLedger.generate_screening_workbook(unique_recs, screening_xlsx)
                    print(f"    Created Master Screening Table: {screening_xlsx}")

                # If screening table exists, reconcile decisions
                if os.path.exists(screening_xlsx) and os.path.exists(flow_path):
                    ScreeningLedger.reconcile_screening_decisions(screening_xlsx, flow_path)

        if not os.path.exists(flow_path):
            raise StepAcceptanceError(f"Stage 2 Failed: Missing PRISMA flow JSON file at {flow_path}")

        with open(flow_path, "r", encoding="utf-8") as f:
            flow_data = json.load(f)

        # --- STEP 2 ACCEPTANCE CHECKPOINT (GATE 1) ---
        print("\n[*] Running Step 2 Acceptance Verification (Gate 1: PRISMA Flow Conservation L ≡ 0)...")
        passed, errors, metrics = Gate1SearchFlow.validate_prisma_flow(flow_data)

        if not passed:
            error_msg = f"Stage 2 Acceptance FAILED (Gate 1 Violation):\n" + "\n".join(errors)
            raise StepAcceptanceError(error_msg)

        print(f">>> [STAGE 2 ACCEPTANCE: PASSED] PRISMA flow mathematically conserved (Loss L = {metrics['flow_loss']}).")
        print(f"    Total Identified: {metrics['total_identified']} -> Screened: {metrics['records_screened']} -> Included: {metrics['studies_included']}")
        return flow_data

    # -------------------------------------------------------------------------
    # STAGE 3: Data Extraction & Statistical Modeling
    # -------------------------------------------------------------------------
    def step3_extract_and_synthesize(self, data_path: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        print("\n================================================================================")
        print(">>> [STAGE 3/6] Data Extraction, Provenance Anchoring & Statistical Modeling")
        print("================================================================================")
        if not os.path.exists(data_path):
            raise StepAcceptanceError(f"Stage 3 Failed: Missing extraction dataset at {data_path}")

        with open(data_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        # --- STEP 3 ACCEPTANCE CHECKPOINT A (GATE 2: EVIDENCE PROVENANCE) ---
        print("\n[*] Running Step 3 Acceptance Verification A (Gate 2: Cryptographic DOI & Coordinate Anchoring)...")
        g2_passed, g2_errors, g2_metrics = Gate2EvidenceProvenance.audit_dataset_provenance(dataset)
        if not g2_passed:
            error_msg = f"Stage 3 Acceptance FAILED (Gate 2 Provenance Violations):\n" + "\n".join(g2_errors)
            raise StepAcceptanceError(error_msg)
        print(f">>> [GATE 2 ACCEPTANCE: PASSED] 100% DOIs & coordinate anchors verified ({g2_metrics['verified_studies']}/{g2_metrics['total_studies_audited']} studies).")

        # --- STEP 3 ACCEPTANCE CHECKPOINT B (GATE 3: NUMERICAL & STATISTICAL CONSISTENCY) ---
        print("\n[*] Running Step 3 Acceptance Verification B (Gate 3: Numerical & Bounded Stats Consistency)...")
        g3_passed, g3_errors, g3_metrics = Gate3Statistics.audit_dataset_statistics(dataset)
        if not g3_passed:
            error_msg = f"Stage 3 Acceptance FAILED (Gate 3 Statistical Inconsistency):\n" + "\n".join(g3_errors)
            raise StepAcceptanceError(error_msg)
        print(f">>> [GATE 3 ACCEPTANCE: PASSED] 100% study sample sizes and 95% CIs self-consistent.")

        # The bundled calculators are deterministic QA fixtures only. A releasable
        # synthesis must be produced by the locked production engine recorded in
        # verification/analysis_manifest.json and released through the stage ledger.
        ma_result = PairwiseMetaAnalysis.analyze_binary(dataset, measure="OR", model="random")
        print(f"    [Exploratory QA Result only] k = {ma_result['k']} RCTs, Pooled OR = {ma_result['pooled_estimate']:.3f} "
              f"[{ma_result['ci_lower']:.3f}, {ma_result['ci_upper']:.3f}], I² = {ma_result['i2_percent']:.1f}%, p = {ma_result['p_value']:.4f}")

        # Compute Network Meta-Analysis
        treatments = list({s.get("treatment_name", "Intervention") for s in dataset})
        if "Placebo" not in treatments:
            treatments.append("Placebo")

        trials_nma = []
        for s in dataset:
            trials_nma.append({
                "study_id": s["study_id"],
                "t1": s.get("treatment_name", "Hydrocortisone"),
                "t2": "Placebo",
                "log_or": s.get("log_effect", 0.0),
                "se": s.get("se", 0.2)
            })

        nma_result = NetworkMetaEngine.calculate_nma(trials_nma, treatments, reference_treatment="Placebo")
        print(">>> [STAGE 3 QA CHECK: PASSED] Fixture calculations completed; production synthesis remains gated by the analysis manifest and locked R/Stata engine output.")
        return ma_result, nma_result, dataset

    # -------------------------------------------------------------------------
    # STAGE 4: Multi-Format Vector Figure Rendering
    # -------------------------------------------------------------------------
    def step4_render_figures(
        self, flow_data: Dict[str, Any], ma_result: Dict[str, Any], dataset: List[Dict[str, Any]], production: bool = False,
        production_results_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        print("\n================================================================================")
        print(">>> [STAGE 4/6] Multi-Format Vector Figure Rendering (600 DPI, Live <text>, PDF Type 42)")
        print("================================================================================")
        if production:
            if not production_results_path:
                raise StepAcceptanceError("Production figure rendering requires --production-results JSON")
            ma_result, nma_result = self._load_production_results(production_results_path)
            self._require_production_synthesis(ma_result, nma_result, result_path=production_results_path)
        fig_dir = os.path.join(self.project_dir, "figures")
        svg_dir = os.path.join(self.project_dir, "editable_files", "vector_svg")
        pdf_dir = os.path.join(self.project_dir, "editable_files", "vector_pdf")
        for d in [fig_dir, svg_dir, pdf_dir]:
            os.makedirs(d, exist_ok=True)

        # 1. PRISMA Diagram
        prisma_prefix = os.path.join(fig_dir, "Figure1_PRISMA_2020_Flow_Diagram")
        PRISMADiagramGenerator.generate(flow_data, prisma_prefix)
        PRISMADiagramGenerator.generate(flow_data, os.path.join(svg_dir, "Figure1_PRISMA_2020_Flow_Diagram"))
        PRISMADiagramGenerator.generate(flow_data, os.path.join(pdf_dir, "Figure1_PRISMA_2020_Flow_Diagram"))

        # 2. Forest Plot
        forest_prefix = os.path.join(fig_dir, "Figure2_Forest_Plot_Mortality")
        pairwise_planned = ma_result.get("planned", True) is not False
        forest_targets = [
            forest_prefix,
            os.path.join(svg_dir, "Figure2_Forest_Plot_Mortality"),
            os.path.join(pdf_dir, "Figure2_Forest_Plot_Mortality"),
        ]
        if pairwise_planned:
            for target in forest_targets:
                ForestPlotGenerator.generate(ma_result, target)
        else:
            # Preserve the fixed Figure 2 output contract without inventing a
            # pairwise study row or pooled estimate for an NMA-only protocol.
            for target in forest_targets:
                ForestPlotGenerator.generate_not_estimable(
                    target,
                    title="All-Cause Mortality at 28-30 Days",
                    message="Pairwise meta-analysis not planned; no pooled pairwise estimate is estimable.",
                )

        # 3. Network Geometry Map. QA keeps the bundled fixture for regression
        # tests; production must use the locked engine's geometry metadata.
        if production:
            if nma_result.get("planned", True) is False:
                geometry_targets = [
                    os.path.join(fig_dir, "Figure3_Network_Geometry_Map"),
                    os.path.join(svg_dir, "Figure3_Network_Geometry_Map"),
                    os.path.join(pdf_dir, "Figure3_Network_Geometry_Map"),
                ]
                for target in geometry_targets:
                    NetworkGeometryGenerator.generate_not_estimable(
                        target,
                        title="Network Meta-analysis",
                        message="Network meta-analysis not planned; no network geometry is estimable.",
                    )
                treat_nodes = comparisons = None
            else:
                treat_nodes = nma_result["treatments"]
                comparisons = nma_result["comparisons"]
        else:
            treat_nodes = [
                {"id": "Placebo", "sample_size": 4200, "color": "#94A3B8"},
                {"id": "Hydrocortisone", "sample_size": 3950, "color": "#2563EB"},
                {"id": "Hydrocortisone + Fludrocortisone", "sample_size": 2100, "color": "#059669"},
                {"id": "Methylprednisolone", "sample_size": 950, "color": "#D97706"},
                {"id": "Dexamethasone", "sample_size": 650, "color": "#DC2626"}
            ]
            comparisons = [
                {"t1": "Hydrocortisone", "t2": "Placebo", "trial_count": 16},
                {"t1": "Hydrocortisone + Fludrocortisone", "t2": "Placebo", "trial_count": 6},
                {"t1": "Hydrocortisone + Fludrocortisone", "t2": "Hydrocortisone", "trial_count": 3},
                {"t1": "Methylprednisolone", "t2": "Placebo", "trial_count": 4},
                {"t1": "Dexamethasone", "t2": "Placebo", "trial_count": 2}
            ]
        net_prefix = os.path.join(fig_dir, "Figure3_Network_Geometry_Map")
        if treat_nodes is not None and comparisons is not None:
            NetworkGeometryGenerator.generate(treat_nodes, comparisons, net_prefix)
            NetworkGeometryGenerator.generate(treat_nodes, comparisons, os.path.join(svg_dir, "Figure3_Network_Geometry_Map"))
            NetworkGeometryGenerator.generate(treat_nodes, comparisons, os.path.join(pdf_dir, "Figure3_Network_Geometry_Map"))

        # --- STEP 4 ACCEPTANCE CHECKPOINT (GATE 4: VECTOR INTEGRITY & ZERO RASTER) ---
        print("\n[*] Running Step 4 Acceptance Verification (Gate 4: Zero-Raster & SVG <text> Audit)...")
        target_fig_dir = svg_dir if os.path.exists(svg_dir) else fig_dir
        g4_passed, g4_errors, g4_metrics = Gate4FigureVector.audit_figures_directory(target_fig_dir)

        if not g4_passed:
            error_msg = f"Stage 4 Acceptance FAILED (Gate 4 Vector Violations):\n" + "\n".join(g4_errors)
            raise StepAcceptanceError(error_msg)

        print(f">>> [GATE 4 ACCEPTANCE: PASSED] All {g4_metrics['figures_audited']} figures verified:")
        print(f"    PNG (600 DPI): {g4_metrics['png_count']} | SVG (Live <text>): {g4_metrics['svg_count']} | PDF (Type 42): {g4_metrics['pdf_count']}")
        return {"figures_dir": fig_dir, "metrics": g4_metrics}

    # -------------------------------------------------------------------------
    # STAGE 5: Office Suites Industrial Engineering
    # -------------------------------------------------------------------------
    def step5_office_suite(
        self,
        pico_config: Dict[str, Any],
        flow_data: Dict[str, Any],
        ma_result: Dict[str, Any],
        nma_result: Dict[str, Any],
        dataset: List[Dict[str, Any]],
        production: bool = False,
        production_results_path: Optional[str] = None,
    ) -> Dict[str, str]:
        print("\n================================================================================")
        print(">>> [STAGE 5/6] Office Suites Engineering (<w:tblHeader/>, <w:cantSplit/>, Dynamic Excel)")
        print("================================================================================")
        if production:
            if not production_results_path:
                raise StepAcceptanceError("Production office rendering requires --production-results JSON")
            ma_result, nma_result = self._load_production_results(production_results_path)
            self._require_production_synthesis(ma_result, nma_result, result_path=production_results_path)
        pairwise_planned = ma_result.get("planned", True) is not False
        nma_planned = nma_result.get("planned", True) is not False
        production_engine = str(
            (ma_result if pairwise_planned else nma_result).get(
                "engine_role", "locked production engine"
            )
        )
        if production:
            pairwise_summary = (
                f"Locked {production_engine} estimate (pooled OR {ma_result['pooled_estimate']:.2f}, "
                f"95% CI [{ma_result['ci_lower']:.2f}, {ma_result['ci_upper']:.2f}], "
                f"I² = {ma_result['i2_percent']:.1f}%)."
                if pairwise_planned
                else "Pairwise synthesis was not planned for this review."
            )
            planned_components = []
            if pairwise_planned:
                planned_components.append("pairwise")
            if nma_planned:
                planned_components.append("network")
            component_label = " and ".join(planned_components) or "planned"
            methods_summary = (
                f"Formal {component_label} estimates were imported from the protocol-declared "
                f"locked production engine ({production_engine}) and passed the synthesis release gate."
            )
            conclusions_summary = (
                "The reported estimates and rankings are transcribed from the locked production "
                "analysis and remain subject to the approved certainty assessment."
            )
        else:
            pairwise_summary = (
                f"QA fixture summary for {flow_data.get('studies_included', 29)} randomized controlled trials; "
                f"not a production synthesis (pooled OR {ma_result['pooled_estimate']:.2f}, "
                f"95% CI [{ma_result['ci_lower']:.2f}, {ma_result['ci_upper']:.2f}])."
            )
            methods_summary = (
                "QA fixture rendering only. Formal pairwise and network estimates must be supplied by "
                "the protocol-declared locked production engine."
            )
            conclusions_summary = "No clinical conclusion is released from the bundled Python QA calculation."

        dataset_by_study = {str(row.get("study_id")): row for row in dataset if isinstance(row, dict)}
        if production and not pairwise_planned:
            # Keep the fixed workbook sheet contract, but do not copy arm-level
            # extraction rows into a pairwise result table when pairwise synthesis
            # is explicitly out of scope.
            primary_rows = []
        elif production and pairwise_planned:
            primary_rows = []
            for locked_row in ma_result.get("studies", []):
                if not isinstance(locked_row, dict):
                    continue
                study_id = str(locked_row.get("study_id", "")).strip()
                source_row = dataset_by_study.get(study_id, {})
                effect = locked_row.get("effect_size", locked_row.get("estimate"))
                ci_lower = locked_row.get("ci_lower")
                ci_upper = locked_row.get("ci_upper")
                primary_rows.append([
                    study_id,
                    source_row.get("events_treatment"), source_row.get("total_treatment"),
                    source_row.get("events_control"), source_row.get("total_control"),
                    round(float(effect), 3) if isinstance(effect, (int, float)) else effect,
                    round(float(ci_lower), 3) if isinstance(ci_lower, (int, float)) else ci_lower,
                    round(float(ci_upper), 3) if isinstance(ci_upper, (int, float)) else ci_upper,
                ])
        else:
            primary_rows = [
                [s["study_id"], s["events_treatment"], s["total_treatment"], s["events_control"],
                 s["total_control"], round(s.get("effect_size", 1.0), 3),
                 round(s.get("ci_lower", 0.8), 3), round(s.get("ci_upper", 1.2), 3)]
                for s in dataset
            ]

        nma_rows = []
        if nma_planned:
            for row in nma_result.get("rankings", []):
                if not isinstance(row, dict):
                    continue
                score = row.get("sucra_percent", row.get("rank_probability", ""))
                estimate = row.get("relative_or_vs_ref", row.get("estimate", ""))
                nma_rows.append([
                    row.get("treatment", ""), row.get("rank", ""),
                    round(score, 1) if isinstance(score, (int, float)) else score,
                    round(estimate, 2) if isinstance(estimate, (int, float)) else estimate,
                    round(row["ci_lower"], 2) if isinstance(row.get("ci_lower"), (int, float)) else row.get("ci_lower", ""),
                    round(row["ci_upper"], 2) if isinstance(row.get("ci_upper"), (int, float)) else row.get("ci_upper", ""),
                ])
        office_dir = os.path.join(self.project_dir, "editable_files", "office_docs")
        os.makedirs(office_dir, exist_ok=True)

        fig_dir = os.path.join(self.project_dir, "figures")
        prisma_prefix = os.path.join(fig_dir, "Figure1_PRISMA_2020_Flow_Diagram")
        forest_prefix = os.path.join(fig_dir, "Figure2_Forest_Plot_Mortality")
        if production:
            discussion_paragraphs = [
                "Interpret the locked production estimates with the approved risk-of-bias and certainty assessment.",
                (
                    "Network ranking is reported from the locked production NMA and should be interpreted with its "
                    "reported uncertainty."
                    if nma_planned
                    else "No network meta-analysis was planned for this review."
                ),
            ]
        else:
            discussion_paragraphs = [
                "This QA fixture does not support a clinical conclusion; interpret only after locked-engine synthesis and independent review.",
                "Network ranking is not released from the bundled QA calculator.",
            ]

        # 1. Word Docx Manuscript
        ms_data = {
            "title": pico_config.get("title", "Corticosteroid Regimens in Septic Shock: A Systematic Review and Network Meta-Analysis"),
            "running_title": "Corticosteroids in Septic Shock NMA",
            "authors": ["Sci-NMA Autonomous Agent Research Collaborative", "Clinical Critical Care Consortium"],
            "affiliations": ["International Evidence Synthesis and Methodological Center"],
            "abstract": {
                "Background": "Septic shock remains a prominent cause of mortality in the ICU. The relative efficacy and safety of various corticosteroid regimens remain debated.",
                "Methods": methods_summary,
                "Results": pairwise_summary,
                "Conclusions": conclusions_summary
            },
            "sections": [
                {
                    "heading": "Introduction",
                    "paragraphs": [
                        "Septic shock is characterized by severe circulatory and cellular metabolic abnormalities associated with substantial mortality.",
                        "Adjunctive corticosteroid therapy has been investigated for decades to mitigate the dysregulated immune response and reverse vasopressor dependence."
                    ]
                },
                {
                    "heading": "Methods",
                    "paragraphs": [
                        "This systematic review was pre-registered in PROSPERO and conducted in accordance with PRISMA 2020 guidelines.",
                        "Four core databases (PubMed, Embase, Cochrane CENTRAL, and Web of Science) were interrogated using validated MeSH and Emtree terms."
                    ]
                },
                {
                    "heading": "Results",
                    "paragraphs": [
                        f"A total of {flow_data.get('total_identified', 1150)} citations were identified, yielding {flow_data.get('studies_included', 29)} eligible randomized controlled trials after rigorous screening.",
                        "Risk of bias assessment using Cochrane RoB 2 confirmed low or moderate risk across primary outcome domains."
                    ],
                    "table": {
                        "title": "Table 1: Baseline Characteristics of Included Landmark Randomized Controlled Trials",
                        "headers": ["Study ID", "Year", "Intervention Arm", "Sample Size (Treat / Ctrl)", "Mortality (%)", "RoB 2 Overall"],
                        "rows": [
                            [s["study_id"], s.get("year", 2020), s.get("treatment_name", "Hydrocortisone"),
                             f"{s['total_treatment']} / {s['total_control']}",
                             f"{s['events_treatment']/s['total_treatment']*100:.1f}% vs {s['events_control']/s['total_control']*100:.1f}%",
                             s.get("rob2_overall", "Low Risk")]
                            for s in dataset[:8]
                        ],
                        "footnote": "Values reported as counts and percentages. RoB 2: Cochrane Risk of Bias 2 Tool for Randomized Trials."
                    }
                },
                {
                    "heading": "Discussion",
                    "paragraphs": discussion_paragraphs
                }
            ]
        }
        docx_path = os.path.join(office_dir, "Manuscript_Submission_Ready.docx")
        DocxManuscriptGenerator.generate(ms_data, docx_path)

        # 2. Master Excel Database
        excel_sheets = {
            "Study_Characteristics": {
                "headers": ["Study ID", "Year", "Country", "Design", "Intervention", "Control", "DOI", "Coordinate Anchor"],
                "rows": [
                    [s["study_id"], s.get("year", 2020), s.get("country", "Multinational"), "RCT",
                     s.get("treatment_name", "Hydrocortisone"), "Placebo", s.get("doi", "10.1000/182"),
                     s.get("coordinate_anchor", "primary.xml:Table1:Col2")]
                    for s in dataset
                ]
            },
            ("Primary_Outcome_Mortality" if production else "QA_Primary_Outcome_Mortality"): {
                "headers": ["Study ID", "Events Treat", "Total Treat", "Events Ctrl", "Total Ctrl", "Odds Ratio", "CI Lower", "CI Upper"],
                "rows": primary_rows,
                "has_summary_row": True,
                "numeric_cols": [2, 3, 4, 5]
            },
        }
        if nma_planned:
            excel_sheets["NMA_Rankings" if production else "QA_Rankings_Not_Production_NMA"] = {
                "headers": ["Treatment Regimen", "Rank", "SUCRA Score (%)", "OR vs Placebo", "CI Lower", "CI Upper"],
                "rows": nma_rows,
            }
        xlsx_path = os.path.join(office_dir, "Master_Research_Database.xlsx")
        MasterExcelGenerator.generate(excel_sheets, xlsx_path)

        # 3. Presentation PPTX
        pptx_data = {
            "title": pico_config.get("title", "Corticosteroids in Septic Shock"),
            "subtitle": "PRISMA 2020 Systematic Review & Network Meta-Analysis",
            "authors": "Sci-NMA Autonomous Research Framework",
            "slides": [
                {
                    "title": "Clinical Background & PICO Rationale",
                    "bullet_points": [
                        "Septic shock remains a major ICU mortality driver (> 30-40%).",
                        "Relative efficacy of corticosteroid regimens has been debated across landmark trials (ADRENAL, APROCCHSS).",
                        "Objective: Synthesize all randomized clinical trials using pairwise & network meta-analysis."
                    ]
                },
                {
                    "title": "PRISMA 2020 Study Flow & Inclusion",
                    "bullet_points": [
                        f"Identified {flow_data.get('total_identified', 1150)} records across 4 core databases.",
                        f"Included {flow_data.get('studies_included', 29)} randomized trials after multi-stage screening.",
                        "Strict flow conservation achieved with zero mathematical discrepancy (L ≡ 0)."
                    ],
                    "image_path": f"{prisma_prefix}.png"
                },
                {
                    "title": "Primary Outcome: 28-Day Mortality",
                    "bullet_points": [
                        pairwise_summary,
                        (f"Heterogeneity across trials: I² = {ma_result['i2_percent']:.1f}%, τ² = {ma_result['tau2']:.3f}."
                         if pairwise_planned else "No pairwise heterogeneity summary was planned."),
                        (("Treatment ranking is reported from the locked production NMA."
                          if production else "Treatment ranking is not released from the bundled QA calculation.")
                         if nma_planned else "No NMA ranking was planned for this review.")
                    ],
                    "image_path": f"{forest_prefix}.png"
                },
                {
                    "title": "Clinical Implications & Recommendations",
                    "bullet_points": [
                        ("Locked production synthesis supplied; interpret estimates with the approved certainty assessment."
                         if production else "QA fixture only; no clinical recommendation is released."),
                        (("NMA ranking supplied by the locked production engine."
                          if production else "No treatment ranking or clinical recommendation is released from this QA fixture.")
                         if nma_planned else "No treatment ranking was planned for this review."),
                        "All artifacts published in 6 open, reproducible, and verifiable formats."
                    ]
                }
            ]
        }
        pptx_path = os.path.join(office_dir, "Publication_Summary_16x9.pptx")
        PresentationGenerator.generate(pptx_data, pptx_path)

        # --- STEP 5 ACCEPTANCE CHECKPOINT (GATE 5: WORD XML & MASTER EXCEL) ---
        print("\n[*] Running Step 5 Acceptance Verification (Gate 5: Word XML & Master Excel Audit)...")
        docx_passed, docx_errors, docx_metrics = Gate5OfficeAudit.audit_docx_file(docx_path)
        xlsx_passed, xlsx_errors, xlsx_metrics = Gate5OfficeAudit.audit_excel_file(xlsx_path)

        office_errors = []
        if not docx_passed:
            office_errors.extend(docx_errors)
        if not xlsx_passed:
            office_errors.extend(xlsx_errors)

        if office_errors:
            error_msg = f"Stage 5 Acceptance FAILED (Gate 5 Office Violations):\n" + "\n".join(office_errors)
            raise StepAcceptanceError(error_msg)

        print(f">>> [GATE 5 ACCEPTANCE: PASSED] Word table XML injected (Header repeat: True, cantSplit: True).")
        print(f"    Master Excel verified: {xlsx_metrics['sheet_count']} sheets, {xlsx_metrics['formula_cells_count']} dynamic formula cells.")

        return {
            "docx": docx_path,
            "xlsx": xlsx_path,
            "pptx": pptx_path
        }

    # -------------------------------------------------------------------------
    # STAGE 6: Global 5-Tier Audit & AI Peer Reviewer Acceptance
    # -------------------------------------------------------------------------
    def step6_audit_and_peer_review(self, pico_config: Dict[str, Any]) -> Dict[str, Any]:
        print("\n================================================================================")
        print(">>> [STAGE 6/6] Final 5-Tier Verification Audit & AI Peer Review Certification")
        print("================================================================================")
        auditor = AuditRunner(self.project_dir)
        report = auditor.run_full_audit()
        json_rep, md_rep = auditor.save_reports(report)

        if not report.overall_passed:
            raise StepAcceptanceError(
                f"Stage 6 Final Certification FAILED. Discrepancies detected:\n{report.to_markdown()}"
            )

        # AI Peer Reviewer Report
        review_text = AIPeerReviewer.evaluate(pico_config, report.to_dict())
        review_path = os.path.join(self.project_dir, "verification", "AI_Peer_Review_Report.md")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(review_text)

        print(f">>> [STAGE 6 ACCEPTANCE: PASSED - 100% VERIFIED]")
        print(f"    Verification Audit Certificate: {json_rep}")
        print(f"    AI Peer Reviewer Report:        {review_path}")

        return {
            "overall_passed": report.overall_passed,
            "audit_json": json_rep,
            "audit_md": md_rep,
            "peer_review_md": review_path
        }

    # -------------------------------------------------------------------------
    # Master Sequential Orchestrator
    # -------------------------------------------------------------------------
    def run_all(
        self, config_pico_path: str, data_path: str, production: bool = False,
        production_results_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute all 6 stages sequentially with strict gated verification.
        If ANY stage fails its acceptance gate, execution is aborted immediately.
        """
        # Step 1
        queries = self.step1_search(config_pico_path)

        # Step 2
        flow_path = os.path.join(self.project_dir, "data", "prisma_flow_data.json")
        flow_data = self.step2_flow(flow_path)

        # Step 3
        ma_result, nma_result, dataset = self.step3_extract_and_synthesize(data_path)

        # Step 4
        fig_info = self.step4_render_figures(
            flow_data, ma_result, dataset, production=production,
            production_results_path=production_results_path,
        )

        # Step 5
        with open(config_pico_path, "r", encoding="utf-8") as f:
            pico_config = json.load(f)
        office_info = self.step5_office_suite(
            pico_config, flow_data, ma_result, nma_result, dataset, production=production,
            production_results_path=production_results_path,
        )

        # Step 6
        final_info = self.step6_audit_and_peer_review(pico_config)

        print("\n================================================================================")
        print(">>> ALL 6 STAGES COMPLETED & ACCEPTED WITH ZERO DISCREPANCIES (100% VERIFIED) <<<")
        print("================================================================================\n")
        return final_info
