"""Build the public sample PDF from its editable Markdown source.

Requires reportlab. Run from any directory:
    python3 scripts/build_sample_report.py
"""
from pathlib import Path
import html
import re
import reportlab

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sample-workflow/workflow-blueprint-sample.md'
OUTPUT = ROOT / 'sample-workflow/workflow-blueprint-sample.pdf'
PINE = colors.HexColor('#132e28')
MINT = colors.HexColor('#edf4f0')
INK = colors.HexColor('#263f37')
MUTED = colors.HexColor('#51665e')
WIDTH = letter[0] - 88
FONT_DIR = Path(reportlab.__file__).resolve().parent / 'fonts'
pdfmetrics.registerFont(TTFont('SampleSans', str(FONT_DIR / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('SampleSans-Bold', str(FONT_DIR / 'VeraBd.ttf')))
pdfmetrics.registerFontFamily('SampleSans', normal='SampleSans', bold='SampleSans-Bold')

styles = {
    'body': ParagraphStyle('Body', fontName='SampleSans', fontSize=10, leading=14.5, textColor=INK, spaceAfter=8),
    'title': ParagraphStyle('Title', fontName='SampleSans-Bold', fontSize=27, leading=31, textColor=PINE, spaceAfter=13),
    'h2': ParagraphStyle('H2', fontName='SampleSans-Bold', fontSize=17, leading=22, textColor=PINE, spaceBefore=9, spaceAfter=12, keepWithNext=True),
    'h3': ParagraphStyle('H3', fontName='SampleSans-Bold', fontSize=12, leading=17, textColor=PINE, spaceBefore=12, spaceAfter=9, keepWithNext=True),
    'list': ParagraphStyle('List', fontName='SampleSans', fontSize=10, leading=14.5, textColor=INK, leftIndent=14, firstLineIndent=-14, spaceAfter=7),
    'quote': ParagraphStyle('Quote', fontName='SampleSans', fontSize=11, leading=16, textColor=PINE, backColor=MINT, borderPadding=11, leftIndent=11, rightIndent=11, spaceBefore=8, spaceAfter=18),
    'cell': ParagraphStyle('Cell', fontName='SampleSans', fontSize=9.5, leading=13, textColor=INK, alignment=TA_LEFT),
    'thead': ParagraphStyle('TableHead', fontName='SampleSans-Bold', fontSize=9.5, leading=13, textColor=colors.white),
}

def inline(text):
    text = html.escape(text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '<a href="' + m.group(2) + '" color="#1c654f"><u>' + m.group(1) + '</u></a>', text)
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

def paragraph(text, style='body'):
    return Paragraph(inline(text), styles[style])

def table(lines):
    rows = [[part.strip() for part in line.strip().strip('|').split('|')] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r':?-+:?', cell.replace(' ', '')) for cell in row)]
    cells = [[paragraph(cell, 'thead' if n == 0 else 'cell') for cell in row] for n, row in enumerate(rows)]
    result = Table(cells, colWidths=[WIDTH * .32, WIDTH * .68], repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, MINT]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, 0), .5, PINE),
    ]))
    return result

def header_footer(pdf, doc):
    pdf.saveState()
    pdf.setFillColor(PINE)
    pdf.setFont('SampleSans-Bold', 11)
    pdf.drawString(44, letter[1] - 35, 'KAVIK WORKS')
    pdf.setFillColor(MUTED)
    pdf.setFont('SampleSans', 8)
    pdf.drawRightString(letter[0] - 44, letter[1] - 35, 'WORKFLOW BLUEPRINT / SAMPLE V1')
    pdf.setStrokeColor(colors.HexColor('#d5e1db'))
    pdf.line(44, letter[1] - 46, letter[0] - 44, letter[1] - 46)
    pdf.line(44, 38, letter[0] - 44, 38)
    pdf.setFont('SampleSans', 8)
    pdf.drawString(44, 24, 'Illustrative planning example | kavikworks.com/sample-workflow/')
    pdf.drawRightString(letter[0] - 44, 24, f'{doc.page} / 4')
    pdf.restoreState()

def build():
    lines = SOURCE.read_text().splitlines()
    story = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == '<!-- pagebreak -->':
            story.append(PageBreak())
        elif line.startswith('|'):
            block = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                block.append(lines[i])
                i += 1
            story.extend([table(block), Spacer(1, 12)])
            continue
        elif line.startswith('# '):
            story.append(paragraph(line[2:], 'title'))
        elif line.startswith('## '):
            story.append(paragraph(line[3:], 'h2'))
        elif line.startswith('### '):
            story.append(paragraph(line[4:], 'h3'))
        elif line.startswith('> '):
            story.append(paragraph(line[2:], 'quote'))
        elif line.startswith('- ') or re.match(r'^\d+\. ', line):
            story.append(paragraph(line, 'list'))
        else:
            block = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '|', '>', '-', '<!--')) and not re.match(r'^\d+\. ', lines[i]):
                block.append(lines[i].strip())
                i += 1
            story.append(paragraph(' '.join(block)))
            continue
        i += 1
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=letter, rightMargin=44, leftMargin=44,
        topMargin=65, bottomMargin=53, title='Workflow Blueprint sample - Kavik Works',
        author='Kavik Works', subject='Illustrative quote-request planning example', allowSplitting=1)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer,
        canvasmaker=lambda *a, **kw: canvas.Canvas(*a, **dict(kw, invariant=1)))
    if doc.page != 4:
        raise ValueError(f'Expected four sample pages, got {doc.page}; review layout before publishing.')
    print(f'Built {OUTPUT}')

if __name__ == '__main__':
    build()
