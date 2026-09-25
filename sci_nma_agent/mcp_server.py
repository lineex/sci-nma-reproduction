"""
Model Context Protocol (MCP) Server for sci-nma-agent.
Exposes evidence synthesis, statistical calculation, and 5-tier verification tools
to any MCP-compatible AI agent (Claude Desktop, Cursor, Antigravity, etc.).
"""

import sys
import json
from typing import Dict, Any, List
from .databases.query_harmonizer import QueryHarmonizer
from .core.gate1_search_flow import Gate1SearchFlow
from .meta_engine.pairwise import PairwiseMetaAnalysis
from .core.audit_runner import AuditRunner


def handle_call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch tool calls for MCP interface."""
    if tool_name == "build_search_query":
        pico = arguments.get("pico", {})
        queries = QueryHarmonizer.harmonize(pico)
        return {"content": [{"type": "text", "text": json.dumps(queries, indent=2)}]}

    elif tool_name == "validate_prisma_flow":
        flow_data = arguments.get("flow_data", {})
        passed, errors, metrics = Gate1SearchFlow.validate_prisma_flow(flow_data)
        res = {"passed": passed, "errors": errors, "metrics": metrics}
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}

    elif tool_name == "run_pairwise_meta":
        studies = arguments.get("studies", [])
        measure = arguments.get("measure", "OR")
        model = arguments.get("model", "random")
        res = PairwiseMetaAnalysis.analyze_binary(studies, measure=measure, model=model)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}

    elif tool_name == "run_5tier_audit":
        project_dir = arguments.get("project_dir", ".")
        auditor = AuditRunner(project_dir)
        rep = auditor.run_full_audit()
        return {"content": [{"type": "text", "text": rep.to_markdown()}]}

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def main():
    """Simple stdio JSON-RPC loop for MCP compatibility."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # In production, uses standard MCP library or stdin/stdout JSON-RPC protocol
    tools_def = [
        {
            "name": "build_search_query",
            "description": "Generate native search queries across PubMed, Embase, Cochrane, WoS, and Scopus from PICO.",
            "inputSchema": {
                "type": "object",
                "properties": {"pico": {"type": "object"}},
                "required": ["pico"]
            }
        },
        {
            "name": "validate_prisma_flow",
            "description": "Audit PRISMA 2020 flow numbers for strict mathematical conservation (L ≡ 0).",
            "inputSchema": {
                "type": "object",
                "properties": {"flow_data": {"type": "object"}},
                "required": ["flow_data"]
            }
        },
        {
            "name": "run_pairwise_meta",
            "description": "Run the bundled exploratory pairwise QA calculator; production synthesis must use the locked protocol-declared engine and analysis manifest.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "studies": {"type": "array"},
                    "measure": {"type": "string", "enum": ["OR", "RR", "RD"]},
                    "model": {"type": "string", "enum": ["random", "fixed"]}
                },
                "required": ["studies"]
            }
        },
        {
            "name": "run_5tier_audit",
            "description": "Run the complete 5-Tier Verification Gates on a review project directory.",
            "inputSchema": {
                "type": "object",
                "properties": {"project_dir": {"type": "string"}},
                "required": ["project_dir"]
            }
        }
    ]

    print(json.dumps({"status": "ready", "tools": tools_def}, indent=2))


if __name__ == "__main__":
    main()
