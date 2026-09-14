"""
Command-Line Interface (CLI) for sci-nma-agent.
Provides subcommands: init, search, ingest, screen-check, session-check, synthesize, render, audit, review, run-all, and run-step.
"""

import sys
import os
import json
import argparse
from .core.audit_runner import AuditRunner
from .workflow.pipeline import SOPPipeline, StepAcceptanceError
from .databases.query_harmonizer import QueryHarmonizer
from .databases.corpus_repository import CorpusRepository
from .databases.deduplicator import ProvenanceDeduplicator
from .databases.audit_ledger import SearchAuditLedger
from .databases.screening_ledger import ScreeningLedger
from .databases.session_manager import BrowserSessionManager, InstitutionalSessionStatus
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

    # Command: audit
    audit_parser = subparsers.add_parser("audit", help="Run 5-Tier Verification Gates on project directory")
    audit_parser.add_argument("project_dir", help="Path to project directory")

    # Command: synthesize
    synth_parser = subparsers.add_parser("synthesize", help="Execute pairwise meta-analysis on dataset")
    synth_parser.add_argument("--data", required=True, help="Path to dataset JSON")

    # Command: run-step
    step_parser = subparsers.add_parser("run-step", help="Execute an individual SOP stage with strict acceptance gate")
    step_parser.add_argument("--stage", type=int, choices=[1, 2, 3, 4, 5, 6], required=True, help="Stage number (1-6)")
    step_parser.add_argument("--project", required=True, help="Path to project directory")
    step_parser.add_argument("--pico", help="Path to PICO config")
    step_parser.add_argument("--data", help="Path to dataset")

    # Command: run-all
    run_parser = subparsers.add_parser("run-all", help="Execute full 6-stage SOP pipeline with step-by-step acceptance gates")
    run_parser.add_argument("--project", required=True, help="Path to project directory")
    run_parser.add_argument("--pico", help="Path to PICO config (default: <project>/config_pico.json)")
    run_parser.add_argument("--data", help="Path to dataset (default: <project>/data/extraction_dataset.json)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        p_dir = args.project_dir
        subdirs = [
            "search_strategies", "data", "figures",
            "editable_files/vector_svg", "editable_files/vector_pdf", "editable_files/office_docs",
            "verification", "original_materials",
            "raw_exports/pubmed", "raw_exports/embase", "raw_exports/wos", "raw_exports/cochrane",
            "screening"
        ]
        for s in subdirs:
            os.makedirs(os.path.join(p_dir, s), exist_ok=True)
        print(f"Initialized review project scaffolding in '{p_dir}'.")
        print("  - Raw export directories ready in: raw_exports/{pubmed, embase, wos, cochrane}")
        print("  - Screening directory ready in: screening/")

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
        print("\n--- Meta-Analysis Result ---")
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
                pipeline.step4_render_figures(flow_data, ma_res, dataset)
            elif args.stage == 5:
                with open(pico_p, "r", encoding="utf-8") as f:
                    pico_config = json.load(f)
                with open(flow_p, "r", encoding="utf-8") as f:
                    flow_data = json.load(f)
                with open(data_p, "r", encoding="utf-8") as f:
                    dataset = json.load(f)
                ma_res, nma_res, _ = pipeline.step3_extract_and_synthesize(data_p)
                pipeline.step5_office_suite(pico_config, flow_data, ma_res, nma_res, dataset)
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
            res = pipeline.run_all(pico_p, data_p)
            print(f"Pipeline run completed. Overall Passed: {res['overall_passed']}")
            sys.exit(0 if res["overall_passed"] else 1)
        except StepAcceptanceError as e:
            print(f"\n[PIPELINE ABORTED] Acceptance gate failure:\n{e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
