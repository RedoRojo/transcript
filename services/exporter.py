import io
import csv
import json
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

def format_srt_time(seconds: float) -> str:
    """Format seconds into 00:00:00,000 for SRT."""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

def format_vtt_time(seconds: float) -> str:
    """Format seconds into 00:00:00.000 for WebVTT."""
    total_ms = int(round(seconds * 1000))
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
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 36, page_text)
        self.drawString(54, 36, "Transcripción de YouTube • Generado automáticamente")
        self.setStrokeColor(colors.HexColor("#e4e4e7"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()

def export_txt(data: Dict[str, Any], include_timestamps: bool = False) -> str:
    """Export transcript as clean text or timestamped text."""
    lines = []
    meta = data.get("metadata", {})
    lang = data.get("current_language", {}).get("language", "Desconocido")
    
    lines.append(f"Título: {meta.get('title', '')}")
    lines.append(f"Canal: {meta.get('author', '')}")
    lines.append(f"URL: {meta.get('url', '')}")
    lines.append(f"Idioma: {lang}")
    lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("-" * 50)
    lines.append("")

    segments = data.get("segments", [])
    if include_timestamps:
        for s in segments:
            lines.append(f"[{s['start_formatted']}] {s['text']}")
    else:
        # Group segments into readable paragraphs (approx every 4-5 segments)
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
    """Export transcript in standard SubRip .srt format."""
    blocks = []
    segments = data.get("segments", [])
    if not segments:
        return "1\n00:00:00,000 --> 00:00:01,000\n[Sin subtítulos]\n"
    for idx, s in enumerate(segments, start=1):
        start_str = format_srt_time(s["start"])
        end_str = format_srt_time(s["end"])
        blocks.append(f"{idx}\n{start_str} --> {end_str}\n{s['text']}\n")
    return "\n".join(blocks)

def export_vtt(data: Dict[str, Any]) -> str:
    """Export transcript in WebVTT format."""
    lines = ["WEBVTT\n"]
    meta = data.get("metadata", {})
    if meta.get("title"):
        lines.append(f"NOTE Título: {meta.get('title')}\n")
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
            s.get("text", "")
        ])
    return output.getvalue()

def export_markdown(data: Dict[str, Any], include_timestamps: bool = True) -> str:
    """Export transcript as Markdown document."""
    meta = data.get("metadata", {})
    lang = data.get("current_language", {}).get("language", "Desconocido")
    stats = data.get("stats", {})

    md = []
    md.append(f"# {meta.get('title', 'Transcripción')}\n")
    md.append(f"- **Canal**: {meta.get('author', 'Desconocido')}")
    md.append(f"- **URL**: [{meta.get('url')}]({meta.get('url')})")
    md.append(f"- **Idioma**: {lang}")
    md.append(f"- **Duración**: {stats.get('duration_formatted', '00:00')}")
    md.append(f"- **Palabras**: {stats.get('total_words', 0)}")
    md.append(f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md.append("---\n")

    segments = data.get("segments", [])
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
        bottomMargin=60
    )

    styles = getSampleStyleSheet()

    # Custom Minimalist Typography & Colors
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#18181b'),
        spaceAfter=6
    )

    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#71717a')
    )

    meta_val_style = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#27272a')
    )

    timestamp_style = ParagraphStyle(
        'Timestamp',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=12,
        textColor=colors.HexColor('#71717a')
    )

    segment_text_style = ParagraphStyle(
        'SegmentText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#18181b')
    )

    story = []

    # Title
    meta = data.get("metadata", {})
    raw_title = meta.get("title", "Transcripción de Video")
    # Escape XML entities for ReportLab Paragraph
    safe_title = raw_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    story.append(Paragraph(safe_title, title_style))
    story.append(Spacer(1, 4))

    # Metadata Table
    lang = data.get("current_language", {}).get("language", "Desconocido")
    stats = data.get("stats", {})
    author = meta.get("author", "YouTube").replace('&', '&amp;')

    meta_data = [
        [
            Paragraph("Canal:", meta_label_style),
            Paragraph(author, meta_val_style),
            Paragraph("Idioma:", meta_label_style),
            Paragraph(lang, meta_val_style)
        ],
        [
            Paragraph("Duración:", meta_label_style),
            Paragraph(stats.get("duration_formatted", "-"), meta_val_style),
            Paragraph("Palabras:", meta_label_style),
            Paragraph(str(stats.get("total_words", "-")), meta_val_style)
        ]
    ]

    meta_table = Table(meta_data, colWidths=[50, 200, 50, 204])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#e4e4e7"), spaceAfter=14))

    segments = data.get("segments", [])

    if include_timestamps:
        # Table of segments with timestamps
        if segments:
            table_rows = []
            for s in segments:
                t_str = f"[{s['start_formatted']}]"
                safe_text = s['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                table_rows.append([
                    Paragraph(t_str, timestamp_style),
                    Paragraph(safe_text, segment_text_style)
                ])
            
            seg_table = Table(table_rows, colWidths=[48, 456])
            seg_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(seg_table)
        else:
            story.append(Paragraph("No se detectaron fragmentos de voz en el audio.", segment_text_style))
    else:
        # Continuous paragraphs
        if segments:
            current_p = []
            for i, s in enumerate(segments):
                safe_text = s['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                current_p.append(safe_text)
                if (i + 1) % 5 == 0:
                    p_text = " ".join(current_p)
                    story.append(Paragraph(p_text, segment_text_style))
                    story.append(Spacer(1, 8))
                    current_p = []
            if current_p:
                p_text = " ".join(current_p)
                story.append(Paragraph(p_text, segment_text_style))
        else:
            story.append(Paragraph("No se detectaron fragmentos de voz en el audio.", segment_text_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
