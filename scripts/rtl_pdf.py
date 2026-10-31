"""Helpers for Arabic (RTL) PDF generation with ReportLab, arabic-reshaper and python-bidi."""
import re, os, glob
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Table, TableStyle, Spacer

BLUE = colors.HexColor("#0B1220"); EM = colors.HexColor("#13B68C"); GREY = colors.HexColor("#CFD6DE"); DARK = colors.HexColor("#222222")
W, H = A4; LM = RM = 15 * mm; CW = W - LM - RM

def find_font(bold=False):
    """يفضّل خط IBM Plex Sans Arabic المرفق في fonts/ ثم DejaVu كبديل."""
    local = Path(__file__).resolve().parents[1] / "fonts" / ("IBMPlexSansArabic-Bold.ttf" if bold else "IBMPlexSansArabic-Regular.ttf")
    if local.exists(): return str(local)
    n = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for root in ["/usr/share/fonts", "/Library/Fonts", "/System/Library/Fonts", "C:/Windows/Fonts", os.path.expanduser("~/.fonts")]:
        hit = glob.glob(os.path.join(root, "**", n), recursive=True)
        if hit: return hit[0]
    import matplotlib
    return os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", n)

SCALE = 1.0   # معامل حجم الخط: يُصغَّر عند استخدام DejaVu البديل (أعرض من Plex) ليبقى التقرير في 6 صفحات
def register():
    global SCALE
    r, b = find_font(), find_font(True)
    SCALE = 1.0 if "IBMPlex" in Path(r).name else 0.89
    pdfmetrics.registerFont(TTFont("R", r)); pdfmetrics.registerFont(TTFont("B", b))

def shape(s): return get_display(arabic_reshaper.reshape(s), base_dir="R")
def sw(s, f, sz): return pdfmetrics.stringWidth(s, f, sz)

class P(Flowable):
    def __init__(s, text, size=9.5, font="R", color=DARK, align="R", lead=None):
        super().__init__(); s.text, s.font, s.color, s.align = re.sub(r"(\d) ر\.س", "\\1\u00a0ر.س", text).replace("أبل باى", "أبل باي"), font, color, align; s.size = size * SCALE; s.lead = (lead or size * 1.65) * SCALE
    def wrap(s, aw, ah):
        s.aw = aw; lines, cur = [], []
        for w in re.split(r"[ \t\r\n]+", s.text.strip()):  # المسافة غير القابلة للكسر (NBSP) تربط الرقم بـ«ر.س» فلا يفصلهما سطر
            w = w.replace("\u00a0", " ")
            if cur and sw(shape(" ".join(cur + [w])), s.font, s.size) > aw: lines.append(" ".join(cur)); cur = [w]
            else: cur.append(w)
        if cur: lines.append(" ".join(cur))
        s.lines = lines or [""]; s.h = s.lead * len(s.lines); return aw, s.h
    def draw(s):
        c = s.canv; c.setFont(s.font, s.size); c.setFillColor(s.color); y = s.h - s.size * 1.15
        for ln in s.lines:
            t = shape(ln)
            (c.drawRightString(s.aw, y, t) if s.align == "R" else c.drawCentredString(s.aw / 2, y, t) if s.align == "C" else c.drawString(0, y, t)); y -= s.lead

def tbl(rows, widths, size=8.6):
    data = []
    for ri, r in enumerate(rows):
        data.append([(P(c, size=size, font="B" if ri == 0 else "R", color=BLUE if ri == 0 else DARK) if isinstance(c, str) else c) for c in r][::-1])
    t = Table(data, colWidths=[w * CW for w in widths][::-1], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .5, GREY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    return t

def h2(text):
    t = Table([[P(text, 12, "B", colors.white)]], colWidths=[CW])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    return [Spacer(1, 9), t, Spacer(1, 6)]
def h3(text): return [Spacer(1, 4), P(text, 10.5, "B", BLUE), Spacer(1, 2)]
def para(text): return P(text, 9.5)
def bullets(items):
    out = []
    for it in items:
        t = Table([[P(it, 9.3), P("•", 9.3, align="C")]], colWidths=[CW - 12, 12])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        out.append(t)
    return out
def callout(text, bar=EM, bg=colors.HexColor("#ECFDF5"), lead=None):
    t = Table([[P((lead + " " if lead else "") + text, 9.3), ""]], colWidths=[CW - 5, 5])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), bg), ("BACKGROUND", (1, 0), (1, 0), bar), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
    return [Spacer(1, 4), t, Spacer(1, 4)]
