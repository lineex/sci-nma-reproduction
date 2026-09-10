"""
Academic Presentation Generator.
Generates 16:9 widescreen PowerPoint presentation slide decks (.pptx)
with clinical decision cards and evidence synthesis summaries.
"""

import os
from typing import Dict, Any, List
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


class PresentationGenerator:
    """Generates 16:9 widescreen academic slide decks."""

    @classmethod
    def generate(
        cls,
        presentation_data: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        presentation_data schema:
        - title: str
        - subtitle: str
        - authors: str
        - slides: List[Dict[str, Any]] (title, bullet_points, optional image_path)
        """
        prs = Presentation()
        # Set 16:9 widescreen aspect ratio: 13.333 x 7.5 inches
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        blank_slide_layout = prs.slide_layouts[6]

        # Colors
        C_TITLE_BG = RGBColor(15, 23, 42)     # Slate 900
        C_SLIDE_BG = RGBColor(248, 250, 252)  # Slate 50
        C_PRIMARY = RGBColor(30, 58, 138)     # Navy Blue
        C_TEXT_DARK = RGBColor(15, 23, 42)
        C_TEXT_MUTED = RGBColor(100, 116, 139)
        C_ACCENT = RGBColor(217, 119, 6)      # Amber

        # 1. Title Slide
        slide1 = prs.slides.add_slide(blank_slide_layout)

        # Title Box
        tx_box = slide1.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(11.333), Inches(3.0))
        tf = tx_box.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.text = presentation_data.get("title", "Clinical Evidence Synthesis")
        p1.font.name = "Arial"
        p1.font.size = Pt(36)
        p1.font.bold = True
        p1.font.color.rgb = C_PRIMARY

        p2 = tf.add_paragraph()
        p2.text = presentation_data.get("subtitle", "Systematic Review & Network Meta-Analysis")
        p2.font.name = "Arial"
        p2.font.size = Pt(20)
        p2.font.color.rgb = C_ACCENT
        p2.space_before = Pt(14)

        p3 = tf.add_paragraph()
        p3.text = presentation_data.get("authors", "Sci-NMA Research Consortium")
        p3.font.name = "Arial"
        p3.font.size = Pt(14)
        p3.font.color.rgb = C_TEXT_MUTED
        p3.space_before = Pt(24)

        # 2. Content Slides
        slides_list = presentation_data.get("slides", [])
        for s_info in slides_list:
            slide = prs.slides.add_slide(blank_slide_layout)

            # Slide Header Banner
            header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(0.9))
            htf = header_box.text_frame
            hp = htf.paragraphs[0]
            hp.text = s_info.get("title", "Section Title")
            hp.font.name = "Arial"
            hp.font.size = Pt(24)
            hp.font.bold = True
            hp.font.color.rgb = C_PRIMARY

            # Content Box
            img_path = s_info.get("image_path")
            has_img = img_path and os.path.exists(img_path)

            text_width = Inches(5.8) if has_img else Inches(11.7)
            body_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), text_width, Inches(5.0))
            btf = body_box.text_frame
            btf.word_wrap = True

            bullets = s_info.get("bullet_points", [])
            for idx, b_text in enumerate(bullets):
                bp = btf.paragraphs[0] if idx == 0 else btf.add_paragraph()
                bp.text = f"•  {b_text}"
                bp.font.name = "Arial"
                bp.font.size = Pt(16)
                bp.font.color.rgb = C_TEXT_DARK
                bp.space_before = Pt(10)

            # Optional Image insertion
            if has_img:
                slide.shapes.add_picture(
                    img_path,
                    Inches(6.9), Inches(1.8),
                    width=Inches(5.6)
                )

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        prs.save(output_path)
        return output_path
