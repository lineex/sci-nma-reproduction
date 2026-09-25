"""
Command-Line Interface (CLI) for sci-nma-agent.
Provides subcommands: init, search, ingest, screen-check, session-check, synthesize, render, audit, review, run-all, and run-step.
"""

import sys
import os
import json
import asyncio
import argparse
import uuid
from importlib.resources import files
from pathlib import Path
from .core.audit_runner import AuditRunner
from .workflow.pipeline import SOPPipeline, StepAcceptanceError
from .databases.query_harmonizer import QueryHarmonizer
from .databases.corpus_repository import CorpusRepository
from .databases.deduplicator import ProvenanceDeduplicator
from .databases.audit_ledger import SearchAuditLedger
from .databases.screening_ledger import ScreeningLedger
from .databases.session_manager import BrowserSessionManager, InstitutionalSessionStatus
from .databases.zotero import ZoteroFullTextBridge, ZoteroLibrary, ZoteroError
from .databases.zotero_mcp import (
    CollectionNotFound,
    MCPToolCallError,
    ZoteroMCPError,
    ZoteroMCPReadClient,
)
from .workflow.stage_ledger import AgentStageLedger, StageLedgerError, STAGE_IDS
from .workflow.manual_fulltext_queue import (
    ManualFullTextQueueError,
    build_manual_fulltext_queue,
    confirm_zotero_attachment,
    validate_manual_fulltext_queue_file,
)
from .meta_engine.pairwise import PairwiseMetaAnalysis


def main():
    # Force UTF-8 encoding across streams
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="sci-nma-agent",
        description="Top-Tier Medical Review & NMA Autonomous Agent CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize a new review project directory")
    init_parser.add_argument("project_dir", help="Path to project directory")

    # Command: search
    search_parser = subparsers.add_parser("search", help="Build search strings for PubMed, Embase, Cochrane, WoS")
    search_parser.add_argument("--pico", required=True, help="Path to PICO JSON configuration")

    # Command: session-check
    sess_parser = subparsers.add_parser("session-check", help="Check browser remote debugging connection and institutional access")
    sess_parser.add_argument("--url", default="http://127.0.0.1:9222", help="Remote debugging CDP URL")

    # Command: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest all raw batch export files, deduplicate, and build screening workbook")
    ingest_parser.add_argument("project_dir", help="Path to project directory")
    ingest_parser.add_argument("--hits", help="Optional JSON file mapping database name to reported hit count")

    # Command: screen-check
    screen_parser = subparsers.add_parser("screen-check", help="Reconcile decisions from master screening workbook and verify PRISMA flow closure")
    screen_parser.add_argument("project_dir", help="Path to project directory")
    screen_parser.add_argument("--table", help="Path to master screening Excel workbook (default: <project>/screening/master_screening_table.xlsx)")

    # Command: Zotero full-text bridge
    zotero_parser = subparsers.add_parser(
        "zotero-fulltext",
        help="Read a Zotero collection, archive attachments, extract text, and write a provenance manifest",
    )
    zotero_parser.add_argument("--project", required=True, help="Review project directory")
    zotero_parser.add_argument("--source", required=True, help="Zotero data directory or Zotero JSON export")
    zotero_parser.add_argument("--collection", help="Zotero collection name, key, or path")
    zotero_parser.add_argument("--screening-table", help="Optional master screening workbook to update retrieval columns")
    zotero_parser.add_argument("--no-copy-pdfs", action="store_true", help="Keep original PDFs in Zotero storage")
    zotero_parser.add_argument("--no-inline-text", action="store_true", help="Keep extracted text in per-item files only")

    # Command: inspect the configured Zotero MCP endpoint without reading library content
    zotero_mcp_parser = subparsers.add_parser(
        "zotero-mcp-check",
        help="Connect to Zotero MCP and list the server's currently advertised tools",
    )
    zotero_mcp_parser.add_argument(
        "--url",
        default="http://127.0.0.1:23120/mcp",
        help="Zotero MCP Streamable HTTP endpoint",
    )

    zotero_mcp_export_parser = subparsers.add_parser(
        "zotero-mcp-export",
        help="Export one Zotero MCP collection with raw provenance and extracted text",
    )
    zotero_mcp_export_parser.add_argument("--project", required=True, help="Review project directory")
    zotero_mcp_export_parser.add_argument("--collection", required=True, help="Exact Zotero collection name or key")
    zotero_mcp_export_parser.add_argument("--match-by", choices=["name", "key"], help="Require an exact collection-name or collection-key match")
    zotero_mcp_export_parser.add_argument("--page-size", type=int, default=100, help="Requested item page size; server pagination metadata and caps are honored")
    zotero_mcp_export_parser.add_argument(
        "--url",
        default="http://127.0.0.1:23120/mcp",
        help="Zotero MCP Streamable HTTP endpoint",
    )

    # Command: manual full-text handoff and confirmation
    manual_fulltext_parser = subparsers.add_parser(
        "manual-fulltext",
        help="Build, validate, or confirm a report-level manual full-text retrieval queue",
    )
    manual_fulltext_actions = manual_fulltext_parser.add_subparsers(dest="manual_fulltext_action", required=True)
    manual_queue_build = manual_fulltext_actions.add_parser("queue", help="Build and display a queue from the current retrieval manifest")
    manual_queue_build.add_argument("--project", required=True)
    manual_queue_build.add_argument("--manifest", required=True, help="Full-text retrieval manifest path")
    manual_queue_build.add_argument("--study-report-map", required=True, help="Approved study/report map path")
    manual_queue_build.add_argument("--screening-manifest", required=True, help="Approved title/abstract screening manifest path")
    manual_queue_build.add_argument("--output", help="Queue output path inside the review project")

    manual_queue_check = manual_fulltext_actions.add_parser("check", help="Validate queue coverage and its input hashes")
    manual_queue_check.add_argument("--project", required=True)
    manual_queue_check.add_argument("--manifest", required=True)
    manual_queue_check.add_argument("--queue", required=True)
    manual_queue_check.add_argument("--study-report-map", required=True)
    manual_queue_check.add_argument("--screening-manifest", required=True)

    manual_queue_confirm = manual_fulltext_actions.add_parser(
        "confirm", help="Re-read an exact Zotero item/attachment and resume full-text retrieval"
    )
    manual_queue_confirm.add_argument("--project", required=True)
    manual_queue_confirm.add_argument("--manifest", required=True, help="Current retrieval manifest path")
    manual_queue_confirm.add_argument("--queue", required=True, help="Queue bound to the current retrieval manifest")
    manual_queue_confirm.add_argument("--study-report-map", required=True, help="Approved study/report map path")
    manual_queue_confirm.add_argument("--screening-manifest", required=True, help="Approved title/abstract screening manifest path")
    manual_queue_confirm.add_argument("--study-id", required=True)
    manual_queue_confirm.add_argument("--report-id", required=True)
    manual_queue_confirm.add_argument("--item-key", required=True, help="Exact Zotero parent item key")
    manual_queue_confirm.add_argument("--attachment-key", required=True, help="Exact attached Zotero attachment key")
    manual_queue_confirm.add_argument(
        "--attachment-file", required=True,
        help="User-supplied local copy; its byte identity with the Zotero attachment is recorded as unverified",
    )
    manual_queue_confirm.add_argument("--actor", required=True, help="Confirming user's audit identifier")
    manual_queue_confirm.add_argument("--identity-evidence", required=True, help="Brief report-to-item match attestation")
    manual_queue_confirm.add_argument("--agent", required=True, help="Executor agent taking the resumed retrieval stage")
    manual_queue_confirm.add_argument("--agent-session", required=True, help="New orchestration session ID")
    manual_queue_confirm.add_argument("--url", default="http://127.0.0.1:23120/mcp", help="Zotero MCP Streamable HTTP endpoint")

    # Command: review-stage (multi-agent workflow gates)
    stage_parser = subparsers.add_parser(
        "review-stage",
        help="Manage the new-review agent stage ledger and two-reviewer release gates",
    )
    stage_actions = stage_parser.add_subparsers(dest="stage_action", required=True)
    stage_init = stage_actions.add_parser("init", help="Create the agent stage ledger")
    stage_init.add_argument("--project", required=True)
    stage_init.add_argument("--overwrite", action="store_true")
    stage_status = stage_actions.add_parser("status", help="Show stage status and ledger integrity")
    stage_status.add_argument("--project", required=True)
    stage_start = stage_actions.add_parser("start", help="Start or resume one stage")
    stage_start.add_argument("--project", required=True)
    stage_start.add_argument("--stage", choices=STAGE_IDS, required=True)
    stage_start.add_argument("--agent", required=True)
    stage_start.add_argument("--agent-session", required=True, help="Unique orchestration session ID for this executor run")
    stage_start.add_argument("--rerun", action="store_true", help="Invalidate this stage and all downstream approvals")
    stage_resume = stage_actions.add_parser("resume", help="Resume or hand off an interrupted stage with ledger history preserved")
    stage_resume.add_argument("--project", required=True)
    stage_resume.add_argument("--stage", choices=STAGE_IDS, required=True)
    stage_resume.add_argument("--agent", required=True)
    stage_resume.add_argument("--agent-session", required=True)
    stage_submit = stage_actions.add_parser("submit", help="Submit stage artifacts for independent review")
    stage_submit.add_argument("--project", required=True)
    stage_submit.add_argument("--stage", choices=STAGE_IDS, required=True)
    stage_submit.add_argument("--agent", required=True)
    stage_submit.add_argument("--agent-session", required=True, help="Must match the session ID used to start this stage")
    stage_submit.add_argument("--artifact", action="append", required=True, help="Artifact path inside project; repeat as needed")
    stage_submit.add_argument("--summary", required=True)
    stage_review = stage_actions.add_parser("review", help="Record an independent approve/revise vote")
    stage_review.add_argument("--project", required=True)
    stage_review.add_argument("--stage", choices=STAGE_IDS, required=True)
    stage_review.add_argument("--reviewer", required=True)
    stage_review.add_argument("--reviewer-session", required=True, help="Unique orchestration session ID for this independent reviewer")
    stage_review.add_argument("--verdict", choices=["approve", "revise"], required=True)
    stage_review.add_argument("--report", required=True, help="Review report path inside project")
    stage_review.add_argument("--findings", required=True, help="Evidence-based findings supporting the verdict")

    # Command: audit
    audit_parser = subparsers.add_parser("audit", help="Run 5-Tier Verification Gates on project directory")
    audit_parser.add_argument("project_dir", help="Path to project directory")

    # Command: synthesize
    synth_parser = subparsers.add_parser(
        "synthesize",
        help="Run the bundled exploratory QA calculator; production release requires a locked analysis manifest",
    )
    synth_parser.add_argument("--data", required=True, help="Path to dataset JSON")

    # Command: run-step
    step_parser = subparsers.add_parser("run-step", help="Execute an individual SOP stage with strict acceptance gate")
    step_parser.add_argument("--stage", type=int, choices=[1, 2, 3, 4, 5, 6], required=True, help="Stage number (1-6)")
    step_parser.add_argument("--project", required=True, help="Path to project directory")
    step_parser.add_argument("--pico", help="Path to PICO config")
    step_parser.add_argument("--data", help="Path to dataset")
    step_parser.add_argument("--production", action="store_true", help="Require locked external production synthesis evidence")
    step_parser.add_argument(
        "--production-results",
        help="Project-relative JSON containing locked pairwise/network production results (required with --production)",
    )

    # Command: run-all
    run_parser = subparsers.add_parser("run-all", help="Execute full 6-stage SOP pipeline with step-by-step acceptance gates")
    run_parser.add_argument("--project", required=True, help="Path to project directory")
    run_parser.add_argument("--pico", help="Path to PICO config (default: <project>/config_pico.json)")
    run_parser.add_argument("--data", help="Path to dataset (default: <project>/data/extraction_dataset.json)")
    run_parser.add_argument("--production", action="store_true", help="Require locked external production synthesis evidence")
    run_parser.add_argument(
        "--production-results",
        help="Project-relative JSON containing locked pairwise/network production results (required with --production)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        p_dir = args.project_dir
        subdirs = [
            "search_strategies", "data", "figures",
            "editable_files/vector_svg", "editable_files/vector_pdf", "editable_files/office_docs",
            "verification", "verification/reviews", "original_materials", "agents",
            "raw_exports/pubmed", "raw_exports/embase", "raw_exports/wos", "raw_exports/cochrane",
            "screening"
        ]
        for s in subdirs:
            os.makedirs(os.path.join(p_dir, s), exist_ok=True)
        project_path = Path(p_dir).expanduser().resolve()
        template_targets = {
            "review_protocol_template.json": "review_protocol.json",
            "methods_source_log_template.json": "verification/methods_source_log.json",
            "data_extraction_template.csv": "data/data_extraction_template.csv",
            "agent_stage_card_template.json": "agents/stage_card_template.json",
            "nma_figure_table_spec_template.json": "data/nma_figure_table_spec_template.json",
            "title_abstract_screening_manifest_template.json": "screening/title_abstract_screening_manifest.json",
            "full_text_retrieval_manifest_template.json": "screening/full_text_retrieval_manifest.json",
            "full_text_screening_manifest_template.json": "screening/full_text_screening_manifest.json",
            "fact_status_manifest_template.json": "data/fact_status_manifest.json",
        }
        for template_name, relative_target in template_targets.items():
            target = project_path / relative_target
            if target.exists():
                continue
            resource = files("sci_nma_agent").joinpath("templates", template_name)
            if resource.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(resource.read_bytes())
        if not (project_path / "verification" / AgentStageLedger.FILENAME).exists():
            AgentStageLedger.initialize(str(project_path))
        print(f"Initialized review project scaffolding in '{p_dir}'.")
        print("  - Raw export directories ready in: raw_exports/{pubmed, embase, wos, cochrane}")
        print("  - Screening directory ready in: screening/")
        print("  - New-review protocol, extraction form, and gated agent ledger initialized.")

    elif args.command == "zotero-fulltext":
        try:
            library = ZoteroLibrary.from_source(args.source)
            bridge = ZoteroFullTextBridge(library)
            result = bridge.materialize(
                project_dir=args.project,
                collection=args.collection,
                copy_pdfs=not args.no_copy_pdfs,
                inline_text=not args.no_inline_text,
            )
            if args.screening_table:
                result["screening_update"] = bridge.update_screening_workbook(
                    args.screening_table, result["manifest_path"]
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0 if not result.get("missing_fulltext") else 2)
        except (ZoteroError, OSError, ValueError) as exc:
            print(f"Zotero full-text import failed: {exc}")
            sys.exit(1)

    elif args.command == "zotero-mcp-check":
        async def inspect_zotero_mcp():
            async with ZoteroMCPReadClient.connect(args.url) as client:
                return [tool.as_dict() for tool in client.tools]

        try:
            tools = asyncio.run(inspect_zotero_mcp())
            print(json.dumps({"endpoint": args.url, "tools": tools}, ensure_ascii=False, indent=2))
            if not tools:
                sys.exit(2)
        except Exception as exc:
            print(f"Zotero MCP check failed: {exc}")
            sys.exit(1)

    elif args.command == "zotero-mcp-export":
        async def export_zotero_mcp():
            async with ZoteroMCPReadClient.connect(args.url) as client:
                return await client.export_collection(
                    args.project,
                    args.collection,
                    page_size=args.page_size,
                    match_by=args.match_by,
                )

        try:
            result = asyncio.run(export_zotero_mcp())
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0 if result.get("pagination_status") == "complete" else 2)
        except MCPToolCallError as exc:
            print(f"Zotero MCP server tool error: {exc}")
            sys.exit(1)
        except CollectionNotFound as exc:
            print(f"Zotero MCP collection resolution failed: {exc}")
            sys.exit(2)
        except (ZoteroMCPError, OSError, ValueError) as exc:
            print(f"Zotero MCP export failed: {exc}")
            sys.exit(1)

    elif args.command == "manual-fulltext":
        try:
            if args.manual_fulltext_action == "queue":
                project = Path(args.project).expanduser().resolve()
                stage = AgentStageLedger(str(project)).status()["stages"]["fulltext_retrieval"]
                run_number = stage["run_count"] if stage["status"] == "in_progress" else stage["run_count"] + 1
                default_output = (
                    Path("screening") / "retrieval_attempts" / f"run-{max(1, run_number):04d}"
                    / "manual_fulltext_queue.json"
                )
                result = build_manual_fulltext_queue(
                    str(project),
                    args.manifest,
                    args.study_report_map,
                    args.screening_manifest,
                    output_path=args.output or str(default_output),
                )
                queue_data = json.loads(Path(result["queue_path"]).read_text(encoding="utf-8"))
                result["records"] = [
                    {
                        key: row.get(key)
                        for key in (
                            "queue_id", "study_id", "report_id", "queue_status",
                            "retrieval_status", "unresolved_reason", "expected_identity",
                            "source_route_attempts", "instructions",
                        )
                    }
                    for row in queue_data.get("records", [])
                    if isinstance(row, dict)
                ]
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.manual_fulltext_action == "check":
                project = Path(args.project).expanduser().resolve()
                result = validate_manual_fulltext_queue_file(
                    str((project / args.queue).resolve() if not Path(args.queue).is_absolute() else Path(args.queue).resolve()),
                    str((project / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest).resolve()),
                    str((project / args.study_report_map).resolve() if not Path(args.study_report_map).is_absolute() else Path(args.study_report_map).resolve()),
                    str((project / args.screening_manifest).resolve() if not Path(args.screening_manifest).is_absolute() else Path(args.screening_manifest).resolve()),
                )
                print(json.dumps({"valid": not result, "errors": result}, ensure_ascii=False, indent=2))
                if result:
                    sys.exit(1)
            else:
                project = Path(args.project).expanduser().resolve()
                controller = AgentStageLedger(str(project))
                snapshot = controller.status()
                controller.validate_resume("fulltext_retrieval", args.agent, args.agent_session)
                retrieval_stage = snapshot["stages"]["fulltext_retrieval"]
                current_status = retrieval_stage["status"]
                expected_run = retrieval_stage["run_count"] if current_status == "in_progress" else retrieval_stage["run_count"] + 1
                expected_run = max(1, expected_run)
                version_id = uuid.uuid4().hex[:12]
                run_dir = (
                    Path("screening") / "retrieval_attempts" / f"run-{expected_run:04d}"
                    / f"resume-{version_id}"
                )

                async def confirm_manual_attachment():
                    async with ZoteroMCPReadClient.connect(args.url) as client:
                        return await confirm_zotero_attachment(
                            project_dir=str(project),
                            retrieval_manifest_path=args.manifest,
                            queue_path=args.queue,
                            study_id=args.study_id,
                            report_id=args.report_id,
                            item_key=args.item_key,
                            attachment_key=args.attachment_key,
                            actor=args.actor,
                            identity_evidence=args.identity_evidence,
                            attachment_file=args.attachment_file,
                            client=client,
                            study_report_map_path=args.study_report_map,
                            screening_manifest_path=args.screening_manifest,
                            output_manifest_path=str(run_dir / "full_text_retrieval_manifest.json"),
                            output_queue_path=str(run_dir / "manual_fulltext_queue.json"),
                            expected_run=expected_run,
                        )

                result = asyncio.run(confirm_manual_attachment())
                try:
                    resumed = controller.resume("fulltext_retrieval", args.agent, args.agent_session)
                except StageLedgerError:
                    for key in (
                        "retrieval_manifest_path", "queue_path", "local_file_path", "content_path"
                    ):
                        output = result.get(key)
                        if not isinstance(output, str) or not output:
                            continue
                        output_path = Path(output).expanduser()
                        output_path = (project / output_path).resolve() if not output_path.is_absolute() else output_path.resolve()
                        try:
                            output_path.relative_to(project)
                        except ValueError:
                            continue
                        output_path.unlink(missing_ok=True)
                    raise
                result["stage_status"] = resumed["stages"]["fulltext_retrieval"]["status"]
                result["stage_run"] = resumed["stages"]["fulltext_retrieval"]["run_count"]
                result["next_action"] = (
                    "Continue full-text retrieval from the versioned manifest; submit the manifest and queue "
                    "for two independent reviews before dependent stages proceed."
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
        except (ManualFullTextQueueError, StageLedgerError, ZoteroMCPError, OSError, ValueError) as exc:
            print(f"Manual full-text operation failed: {exc}")
            sys.exit(1)

    elif args.command == "review-stage":
        try:
            if args.stage_action == "init":
                ledger = AgentStageLedger.initialize(args.project, overwrite=args.overwrite)
            else:
                controller = AgentStageLedger(args.project)
                if args.stage_action == "status":
                    ledger = controller.status()
                elif args.stage_action == "start":
                    ledger = controller.start(args.stage, args.agent, args.agent_session, rerun=args.rerun)
                elif args.stage_action == "resume":
                    ledger = controller.resume(args.stage, args.agent, args.agent_session)
                elif args.stage_action == "submit":
                    ledger = controller.submit(args.stage, args.agent, args.agent_session, args.artifact, args.summary)
                else:
                    ledger = controller.review(
                        args.stage, args.reviewer, args.reviewer_session, args.verdict, args.report, args.findings
                    )
            if args.stage_action == "status":
                summary = {
                    "integrity_valid": ledger.get("integrity_valid"),
                    "evidence_integrity_valid": ledger.get("evidence_integrity_valid"),
                    "current_stage": ledger.get("current_stage"),
                    "stages": {key: value["status"] for key, value in ledger["stages"].items()},
                }
                print(json.dumps(summary, ensure_ascii=False, indent=2))
                if not summary["integrity_valid"] or not summary["evidence_integrity_valid"]:
                    sys.exit(1)
            else:
                stage_id = getattr(args, "stage", None)
                print(json.dumps({
                    "ledger": str(Path(args.project).expanduser().resolve() / "verification" / AgentStageLedger.FILENAME),
                    "stage": stage_id,
                    "status": ledger["stages"].get(stage_id, {}).get("status") if stage_id else "initialized",
                }, ensure_ascii=False, indent=2))
        except (StageLedgerError, OSError, ValueError) as exc:
            print(f"Stage gate rejected operation: {exc}")
            sys.exit(1)

    elif args.command == "session-check":
        mgr = BrowserSessionManager(args.url)
        conn = mgr.is_browser_connected()
        print(f"Browser CDP at {args.url}: {'CONNECTED' if conn else 'NOT CONNECTED'}")
        if conn:
            pages = mgr.get_open_pages()
            print(f"Active browser tabs: {len(pages)}")
            for p in pages:
                print(f"  - [{p.get('title', '')[:50]}] {p.get('url', '')}")
        else:
            print("To enable session reuse with your institutional logins:")
            print('  Launch Chrome with: chrome.exe --remote-debugging-port=9222')

    elif args.command == "search":
        with open(args.pico, "r", encoding="utf-8") as f:
            pico = json.load(f)
        queries = QueryHarmonizer.harmonize(pico)
        print("\n--- Harmonized Multi-Database Search Queries ---\n")
        for db, q in queries.items():
            print(f"[{db}]:\n{q}\n")

    elif args.command == "ingest":
        p_dir = args.project_dir
        raw_dir = os.path.join(p_dir, "raw_exports")
        if not os.path.exists(raw_dir):
            print(f"Error: Missing raw_exports directory at {raw_dir}")
            sys.exit(1)

        print(f"[*] Scanning and ingesting raw batch files from: {raw_dir}")
        ingest_res = CorpusRepository.scan_and_ingest(raw_dir)
        print(f"    Total Landed Records Ingested: {ingest_res['total_raw_records']}")
        for db, stat in ingest_res["databases"].items():
            print(f"    - {db}: {stat['record_count']} records across {stat['file_count']} files")

        print("[*] Running multi-tier deduplication with provenance retention...")
        unique_recs, dedup_metrics, audit_log = ProvenanceDeduplicator.deduplicate(ingest_res["records"])
        print(f"    Net Unique Records to Screen: {dedup_metrics['unique_records']}")
        print(f"    Duplicates Removed: {dedup_metrics['duplicates_removed']}")

        hits_dict = {}
        if args.hits and os.path.exists(args.hits):
            with open(args.hits, "r", encoding="utf-8") as f:
                hits_dict = json.load(f)
        else:
            # Default to landed counts if not provided
            hits_dict = {db: stat["record_count"] for db, stat in ingest_res["databases"].items()}

        queries_dict = {}
        search_dir = os.path.join(p_dir, "search_strategies")
        if os.path.exists(search_dir):
            for f in os.listdir(search_dir):
                if f.endswith("_search.txt"):
                    db_k = f.replace("_search.txt", "").replace("_", " ").title()
                    with open(os.path.join(search_dir, f), "r", encoding="utf-8") as s_file:
                        queries_dict[db_k] = s_file.read()

        ledger = SearchAuditLedger.compile_audit_ledger(queries_dict, hits_dict, ingest_res, dedup_metrics)
        audit_xlsx = os.path.join(p_dir, "verification", "Search_Flow_Audit_Table.xlsx")
        SearchAuditLedger.export_excel_audit_table(ledger, audit_xlsx)
        print(f"    Exported Search Audit Ledger: {audit_xlsx}")

        prisma_flow_draft = os.path.join(p_dir, "data", "prisma_flow_data.json")
        SearchAuditLedger.generate_prisma_flow_json(ledger, prisma_flow_draft)
        print(f"    Drafted PRISMA Flow JSON: {prisma_flow_draft}")

        screening_xlsx = os.path.join(p_dir, "screening", "master_screening_table.xlsx")
        ScreeningLedger.generate_screening_workbook(unique_recs, screening_xlsx)
        print(f"    Generated Master Screening Table: {screening_xlsx}")
        print("\n[SUCCESS] Ingestion & Scaffolding complete. You can now perform Title/Abstract screening in the workbook.")

    elif args.command == "screen-check":
        p_dir = args.project_dir
        table_path = args.table or os.path.join(p_dir, "screening", "master_screening_table.xlsx")
        flow_p = os.path.join(p_dir, "data", "prisma_flow_data.json")

        if not os.path.exists(table_path):
            print(f"Error: Screening workbook not found at {table_path}")
            sys.exit(1)
        if not os.path.exists(flow_p):
            print(f"Error: PRISMA flow JSON not found at {flow_p}")
            sys.exit(1)

        print(f"[*] Reconciling screening decisions from: {table_path}")
        passed, res, errors = ScreeningLedger.reconcile_screening_decisions(table_path, flow_p)
        if not passed:
            print("\n[!] PRISMA Flow Conservation Violation (Gate 1):")
            for e in errors:
                print(f"    - {e}")
            sys.exit(1)

        m = res["metrics"]
        print(f"\n>>> [SCREENING RECONCILIATION PASSED] (L ≡ 0)")
        print(f"    Total Screened:       {m.get('records_screened')}")
        print(f"    TiAb Excluded:        {m.get('records_screened') - m.get('reports_sought')}")
        print(f"    Reports Assessed:     {m.get('reports_assessed')}")
        print(f"    Full-Text Excluded:   {m.get('reports_assessed') - m.get('studies_included')}")
        print(f"    Final Studies Included: {m.get('studies_included')}")
        print(f"    Updated PRISMA flow:  {flow_p}")

    elif args.command == "audit":
        auditor = AuditRunner(args.project_dir)
        report = auditor.run_full_audit()
        j_path, m_path = auditor.save_reports(report)
        print(report.to_markdown())
        print(f"\nAudit completed. Saved reports:\n  JSON: {j_path}\n  MD:   {m_path}")
        sys.exit(0 if report.overall_passed else 1)

    elif args.command == "synthesize":
        with open(args.data, "r", encoding="utf-8") as f:
            data = json.load(f)
        res = PairwiseMetaAnalysis.analyze_binary(data)
        print("\n--- Exploratory QA Result (not a production synthesis) ---")
        print("Production results must come from the protocol-declared locked engine and analysis_manifest.json.")
        print(f"Studies (k): {res['k']}")
        print(f"Pooled OR: {res['pooled_estimate']:.3f} (95% CI: [{res['ci_lower']:.3f}, {res['ci_upper']:.3f}])")
        print(f"Heterogeneity I²: {res['i2_percent']:.1f}%, τ²: {res['tau2']:.4f}, p: {res['p_value']:.4f}")

    elif args.command == "run-step":
        p_dir = args.project
        pico_p = args.pico or os.path.join(p_dir, "config_pico.json")
        data_p = args.data or os.path.join(p_dir, "data", "extraction_dataset.json")
        flow_p = os.path.join(p_dir, "data", "prisma_flow_data.json")

        pipeline = SOPPipeline(p_dir)
        try:
            if args.stage == 1:
                pipeline.step1_search(pico_p)
            elif args.stage == 2:
                pipeline.step2_flow(flow_p)
            elif args.stage == 3:
                pipeline.step3_extract_and_synthesize(data_p)
            elif args.stage == 4:
                with open(flow_p, "r", encoding="utf-8") as f:
                    flow_data = json.load(f)
                with open(data_p, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                ma_res = PairwiseMetaAnalysis.analyze_binary(dataset)
                pipeline.step4_render_figures(
                    flow_data,
                    ma_res,
                    dataset,
                    production=args.production,
                    production_results_path=args.production_results,
                )
            elif args.stage == 5:
                with open(pico_p, "r", encoding="utf-8") as f:
                    pico_config = json.load(f)
                with open(flow_p, "r", encoding="utf-8") as f:
                    flow_data = json.load(f)
                with open(data_p, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                ma_res, nma_res, _ = pipeline.step3_extract_and_synthesize(data_p)
                pipeline.step5_office_suite(
                    pico_config,
                    flow_data,
                    ma_res,
                    nma_res,
                    dataset,
                    production=args.production,
                    production_results_path=args.production_results,
                )
            elif args.stage == 6:
                with open(pico_p, "r", encoding="utf-8") as f:
                    pico_config = json.load(f)
                pipeline.step6_audit_and_peer_review(pico_config)
            print(f"\nStage {args.stage} successfully executed and accepted!")
            sys.exit(0)
        except StepAcceptanceError as e:
            print(f"\n[CRITICAL ERROR] {e}")
            sys.exit(1)

    elif args.command == "run-all":
        p_dir = args.project
        pico_p = args.pico or os.path.join(p_dir, "config_pico.json")
        data_p = args.data or os.path.join(p_dir, "data", "extraction_dataset.json")

        pipeline = SOPPipeline(p_dir)
        try:
            res = pipeline.run_all(
                pico_p,
                data_p,
                production=args.production,
                production_results_path=args.production_results,
            )
            print(f"Pipeline run completed. Overall Passed: {res['overall_passed']}")
            sys.exit(0 if res["overall_passed"] else 1)
        except StepAcceptanceError as e:
            print(f"\n[PIPELINE ABORTED] Acceptance gate failure:\n{e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
