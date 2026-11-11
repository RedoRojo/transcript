import csv
import io
import json
from datetime import datetime
from typing import Any, Dict
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def format_srt_time(seconds: float) -> str:
    """Format seconds into 00:00:00,000 for SubRip (.srt)."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds into 00:00:00.000 for WebVTT (.vtt)."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute total page count."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#71717a"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, page_text)
        self.drawString(54, 36, "Transcript • Auto-generated export")
        self.setStrokeColor(colors.HexColor("#e4e4e7"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()


def export_txt(data: Dict[str, Any], include_timestamps: bool = False) -> str:
    """Export transcript as clean plain text or timestamped text."""
    lines = []
    meta = data.get("metadata", {})
    lang = data.get("current_language", {}).get("language", "Unknown")
    is_local = bool(meta.get("is_local"))

    lines.append(f"Title: {meta.get('title', '')}")
    lines.append(f"Source: {meta.get('author', '')}")
    lines.append(f"{'File' if is_local else 'URL'}: {meta.get('url', '')}")
    lines.append(f"Language: {lang}")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("-" * 50)
    lines.append("")

    segments = data.get("segments", [])
    if not segments:
        lines.append("No speech segments were detected.")
        return "\n".join(lines)

    if include_timestamps:
        for s in segments:
            lines.append(f"[{s['start_formatted']}] {s['text']}")
    else:
        # Group segments into readable paragraphs (approx. every 5 segments)
        current_p = []
        for i, s in enumerate(segments):
            current_p.append(s["text"])
            if (i + 1) % 5 == 0:
                lines.append(" ".join(current_p))
                lines.append("")
                current_p = []
        if current_p:
            lines.append(" ".join(current_p))

    return "\n".join(lines)


def export_srt(data: Dict[str, Any]) -> str:
    """Export transcript in standard SubRip (.srt) format."""
    blocks = []
    segments = data.get("segments", [])
    if not segments:
        return "1\n00:00:00,000 --> 00:00:01,000\n[No speech detected]\n"
    for idx, s in enumerate(segments, start=1):
        start_str = format_srt_time(s["start"])
        end_str = format_srt_time(s["end"])
        blocks.append(f"{idx}\n{start_str} --> {end_str}\n{s['text']}\n")
    return "\n".join(blocks)


def export_vtt(data: Dict[str, Any]) -> str:
    """Export transcript in WebVTT (.vtt) format."""
    lines = ["WEBVTT\n"]
    meta = data.get("metadata", {})
    if meta.get("title"):
        lines.append(f"NOTE Title: {meta.get('title')}\n")
    segments = data.get("segments", [])
    for s in segments:
        start_str = format_vtt_time(s["start"])
        end_str = format_vtt_time(s["end"])
        lines.append(f"{start_str} --> {end_str}\n{s['text']}\n")
    return "\n".join(lines)


def export_json(data: Dict[str, Any]) -> str:
    """Export transcript as structured JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False)


def export_csv(data: Dict[str, Any]) -> str:
    """Export transcript as CSV."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Index", "StartSeconds", "EndSeconds", "StartFormatted", "EndFormatted", "Text"])
    for s in data.get("segments", []):
        writer.writerow([
            s.get("index", ""),
            s.get("start", ""),
            s.get("end", ""),
            s.get("start_formatted", ""),
            s.get("end_formatted", ""),
            s.get("text", ""),
        ])
    return output.getvalue()


def export_markdown(data: Dict[str, Any], include_timestamps: bool = True) -> str:
    """Export transcript as a Markdown document."""
    meta = data.get("metadata", {})
    lang = data.get("current_language", {}).get("language", "Unknown")
    stats = data.get("stats", {})
    is_local = bool(meta.get("is_local"))
    ref_value = meta.get("url", "")

    md = []
    md.append(f"# {meta.get('title', 'Transcript')}\n")
    md.append(f"- **Source**: {meta.get('author', 'Unknown')}")
    if is_local:
        md.append(f"- **File**: `{ref_value}`")
    else:
        md.append(f"- **URL**: [{ref_value}]({ref_value})")
    md.append(f"- **Language**: {lang}")
    md.append(f"- **Duration**: {stats.get('duration_formatted', '00:00')}")
    md.append(f"- **Words**: {stats.get('total_words', 0)}")
    md.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md.append("---\n")

    segments = data.get("segments", [])
    if not segments:
        md.append("_No speech segments were detected._\n")
        return "\n".join(md)

    if include_timestamps:
        for s in segments:
            md.append(f"**`[{s['start_formatted']}]`** {s['text']}\n")
    else:
        current_p = []
        for i, s in enumerate(segments):
            current_p.append(s["text"])
            if (i + 1) % 5 == 0:
                md.append(" ".join(current_p) + "\n")
                current_p = []
        if current_p:
            md.append(" ".join(current_p) + "\n")

    return "\n".join(md)


def export_pdf(data: Dict[str, Any], include_timestamps: bool = True) -> bytes:
    """Generate a clean, minimalist monochrome PDF document."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=60,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#18181b"),
        spaceAfter=6,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#71717a"),
    )

    meta_val_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#27272a"),
    )

    timestamp_style = ParagraphStyle(
        "Timestamp",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#71717a"),
    )

    segment_text_style = ParagraphStyle(
        "SegmentText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#18181b"),
    )

    story = []

    meta = data.get("metadata", {})
    raw_title = meta.get("title", "Video Transcript")
    story.append(Paragraph(xml_escape(str(raw_title)), title_style))
    story.append(Spacer(1, 4))

    lang = xml_escape(str(data.get("current_language", {}).get("language", "Unknown")))
    stats = data.get("stats", {})
    author = xml_escape(str(meta.get("author", "YouTube")))

    meta_data = [
        [
            Paragraph("Source:", meta_label_style),
            Paragraph(author, meta_val_style),
            Paragraph("Language:", meta_label_style),
            Paragraph(lang, meta_val_style),
        ],
        [
            Paragraph("Duration:", meta_label_style),
            Paragraph(xml_escape(str(stats.get("duration_formatted", "-"))), meta_val_style),
            Paragraph("Words:", meta_label_style),
            Paragraph(xml_escape(str(stats.get("total_words", "-"))), meta_val_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[50, 200, 56, 198])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#e4e4e7"), spaceAfter=14))

    segments = data.get("segments", [])

    if include_timestamps:
        if segments:
            table_rows = []
            for s in segments:
                t_str = f"[{s['start_formatted']}]"
                safe_text = xml_escape(str(s["text"]))
                table_rows.append([
                    Paragraph(t_str, timestamp_style),
                    Paragraph(safe_text, segment_text_style),
                ])

            seg_table = Table(table_rows, colWidths=[48, 456])
            seg_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(seg_table)
        else:
            story.append(Paragraph("No speech segments were detected in this audio.", segment_text_style))
    else:
        if segments:
            current_p = []
            for i, s in enumerate(segments):
                safe_text = xml_escape(str(s["text"]))
                current_p.append(safe_text)
                if (i + 1) % 5 == 0:
                    story.append(Paragraph(" ".join(current_p), segment_text_style))
                    story.append(Spacer(1, 8))
                    current_p = []
            if current_p:
                story.append(Paragraph(" ".join(current_p), segment_text_style))
        else:
            story.append(Paragraph("No speech segments were detected in this audio.", segment_text_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
