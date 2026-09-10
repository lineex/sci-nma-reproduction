"""
Unit tests for Gate 4: Zero-Raster Vector Graphics & Anti-Collision.
"""

import os
import pytest
from sci_nma_agent.core.gate4_figure_vector import Gate4FigureVector


def test_audit_svg_with_live_text(tmp_path):
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect width="100" height="100" fill="white"/>
        <text x="10" y="20" font-family="Arial">Live Text Node</text>
    </svg>"""
    svg_file = tmp_path / "test_live_text.svg"
    svg_file.write_text(svg_content, encoding="utf-8")

    passed, errors, metrics = Gate4FigureVector.audit_svg_file(str(svg_file))
    assert passed is True
    assert metrics["has_text_nodes"] is True
    assert metrics["text_count"] == 1
    assert metrics["has_embedded_raster"] is False


def test_audit_svg_rejects_embedded_raster(tmp_path):
    svg_with_raster = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <image href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="/>
        <text x="10" y="20">Text</text>
    </svg>"""
    svg_file = tmp_path / "test_raster.svg"
    svg_file.write_text(svg_with_raster, encoding="utf-8")

    passed, errors, metrics = Gate4FigureVector.audit_svg_file(str(svg_file))
    assert passed is False
    assert any("Embedded base64 raster" in e for e in errors)
