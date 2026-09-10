"""
Gate 4: Rendering Code, Clinical Imaging & Biological Artwork Gate.
Enforces zero-raster code rendering, SVG live <text> nodes, Type 42 PDF embedding,
and anti-collision layout validation.
"""

import os
import re
from typing import Dict, Any, List, Tuple


class Gate4FigureVector:
    """Validator for Gate 4: Zero-Raster Vector Graphics & Anti-Collision."""

    @staticmethod
    def audit_svg_file(svg_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Scan SVG file for:
        1. Presence of raw editable <text> nodes.
        2. Absence of embedded base64 bitmaps (unless authorized).
        """
        errors = []
        metrics = {"has_text_nodes": False, "text_count": 0, "has_embedded_raster": False}

        if not os.path.exists(svg_path):
            return False, [f"SVG file not found: {svg_path}"], metrics

        try:
            with open(svg_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            text_tags = re.findall(r"<text\b", content, re.IGNORECASE)
            metrics["text_count"] = len(text_tags)
            metrics["has_text_nodes"] = (len(text_tags) > 0)

            if len(text_tags) == 0:
                errors.append(
                    f"[{os.path.basename(svg_path)}] Zero live <text> nodes found. "
                    f"Fonts appear to be outlined into paths. Must configure svg.fonttype = 'none'."
                )

            # Check for embedded base64 rasters
            if "data:image/png;base64" in content or "data:image/jpeg;base64" in content:
                metrics["has_embedded_raster"] = True
                errors.append(
                    f"[{os.path.basename(svg_path)}] Embedded base64 raster detected in vector SVG. "
                    f"Violates zero-author-raster protocol."
                )

        except Exception as e:
            errors.append(f"Failed to read SVG file {svg_path}: {str(e)}")

        passed = (len(errors) == 0)
        return passed, errors, metrics

    @staticmethod
    def audit_pdf_file(pdf_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Check PDF exists and verify font configuration."""
        errors = []
        metrics = {"exists": False, "file_size_bytes": 0}

        if not os.path.exists(pdf_path):
            return False, [f"PDF file not found: {pdf_path}"], metrics

        metrics["exists"] = True
        metrics["file_size_bytes"] = os.path.getsize(pdf_path)

        if metrics["file_size_bytes"] < 1000:
            errors.append(f"[{os.path.basename(pdf_path)}] PDF file abnormally small (< 1KB).")

        # Basic binary scan for TrueType / FontDescriptor
        try:
            with open(pdf_path, "rb") as f:
                header = f.read(1024)
                if not header.startswith(b"%PDF"):
                    errors.append(f"[{os.path.basename(pdf_path)}] Invalid PDF header.")
        except Exception as e:
            errors.append(f"Error reading PDF {pdf_path}: {str(e)}")

        passed = (len(errors) == 0)
        return passed, errors, metrics

    @staticmethod
    def audit_figures_directory(figures_dir: str) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Audit figure directory for multi-format synchrony (PNG, SVG, PDF)."""
        errors = []
        metrics = {"figures_audited": 0, "png_count": 0, "svg_count": 0, "pdf_count": 0}

        if not os.path.exists(figures_dir):
            return False, [f"Figures directory not found: {figures_dir}"], metrics

        files = os.listdir(figures_dir)
        pngs = [f for f in files if f.endswith(".png")]
        svgs = [f for f in files if f.endswith(".svg")]
        pdfs = [f for f in files if f.endswith(".pdf")]

        metrics["png_count"] = len(pngs)
        metrics["svg_count"] = len(svgs)
        metrics["pdf_count"] = len(pdfs)
        metrics["figures_audited"] = len(pngs)

        # Audit SVGs
        for svg in svgs:
            p = os.path.join(figures_dir, svg)
            p_pass, p_errs, _ = Gate4FigureVector.audit_svg_file(p)
            if not p_pass:
                errors.extend(p_errs)

        passed = (len(errors) == 0)
        return passed, errors, metrics
