"""
Command-Line Interface (CLI) for sci-nma-agent.
Provides subcommands: init, search, synthesize, render, audit, review, run-all.
"""

import sys
import os
import json
import argparse
from .core.audit_runner import AuditRunner
from .workflow.pipeline import SOPPipeline
from .databases.query_harmonizer import QueryHarmonizer
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

    # Command: audit
    audit_parser = subparsers.add_parser("audit", help="Run 5-Tier Verification Gates on project directory")
    audit_parser.add_argument("project_dir", help="Path to project directory")

    # Command: synthesize
    synth_parser = subparsers.add_parser("synthesize", help="Execute pairwise meta-analysis on dataset")
    synth_parser.add_argument("--data", required=True, help="Path to dataset JSON")

    # Command: run-all
    run_parser = subparsers.add_parser("run-all", help="Execute full 6-stage SOP pipeline")
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
            "verification", "original_materials"
        ]
        for s in subdirs:
            os.makedirs(os.path.join(p_dir, s), exist_ok=True)
        print(f"Initialized review project scaffolding in '{p_dir}'.")

    elif args.command == "search":
        with open(args.pico, "r", encoding="utf-8") as f:
            pico = json.load(f)
        queries = QueryHarmonizer.harmonize(pico)
        print("\n--- Harmonized Multi-Database Search Queries ---\n")
        for db, q in queries.items():
            print(f"[{db}]:\n{q}\n")

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

    elif args.command == "run-all":
        p_dir = args.project
        pico_p = args.pico or os.path.join(p_dir, "config_pico.json")
        data_p = args.data or os.path.join(p_dir, "data", "extraction_dataset.json")

        pipeline = SOPPipeline(p_dir)
        res = pipeline.run_all(pico_p, data_p)
        print(f"\nPipeline run completed. Overall Passed: {res['overall_passed']}")
        sys.exit(0 if res["overall_passed"] else 1)


if __name__ == "__main__":
    main()
