# Sentinel Solution Presentation — v4. A concise, executive-pitch rebuild
# requested 2026-09-28: v3 is factually solid but reads as an engineering
# log (dense hedged prose on almost every slide) rather than a confident
# hackathon pitch. v4 reuses v3's exact visual system (palette, fonts,
# shape helpers — copied verbatim below, unchanged) and cuts every slide
# down to the headline claim + the smallest honest supporting detail.
# Long caveats move to ONE dedicated "Honest Status" slide instead of
# being repeated inline everywhere. No fact is dropped — only compressed.
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

# ---------------------------------------------------------------- palette
NAVY_DEEP = RGBColor(0x07, 0x0D, 0x18)
NAVY = RGBColor(0x0D, 0x16, 0x28)
NAVY_CARD = RGBColor(0x12, 0x1C, 0x30)
BLUE = RGBColor(0x2F, 0x7A, 0xF2)
BLUE_DEEP = RGBColor(0x18, 0x4B, 0xC4)
AMBER = RGBColor(0xF2, 0x9A, 0x1E)
CYAN = RGBColor(0x1E, 0xC9, 0xB7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x61, 0x6E, 0x82)
MUTED_LT = RGBColor(0x8A, 0x96, 0xA8)
SURFACE = RGBColor(0xF4, 0xF6, 0xFA)
SURFACE2 = RGBColor(0xEA, 0xEE, 0xF5)
LINE = RGBColor(0xDE, 0xE4, 0xEC)
GREEN = RGBColor(0x12, 0xA1, 0x6B)
RED = RGBColor(0xE0, 0x4A, 0x4A)
GRAY_STATUS = RGBColor(0x8A, 0x93, 0xA3)

F_TITLE = "Bahnschrift SemiBold"
F_TITLE_LIGHT = "Bahnschrift"
F_BODY = "Segoe UI"
F_BODY_SB = "Segoe UI Semibold"
F_BODY_L = "Segoe UI Semilight"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]
PAGE_NO = [0]
TOTAL = 17


def add_slide():
    return prs.slides.add_slide(BLANK)


def set_bg(slide, color):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def _noshadow(shp):
    shp.shadow.inherit = False
    return shp


def rect(slide, l, t, w, h, fill=None, line=None, line_w=Pt(1)):
    shp = _noshadow(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = line_w
    return shp


def rrect(slide, l, t, w, h, fill=None, line=None, line_w=Pt(1), radius=0.08):
    shp = _noshadow(slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h))
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = line_w
    return shp


def autoshape(slide, kind, l, t, w, h, fill=None, line=None, line_w=Pt(1.5)):
    shp = _noshadow(slide.shapes.add_shape(kind, l, t, w, h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = line_w
    return shp


def txt(slide, l, t, w, h, text, size=18, color=INK, bold=False, italic=False,
        align=PP_ALIGN.LEFT, font=F_BODY, anchor=MSO_ANCHOR.TOP, line_spacing=1.0,
        space_after=0, tracking=None):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    for i, line_text in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = line_text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
        r.font.name = font
    return tb


def bullets(slide, l, t, w, h, items, size=14, color=INK, font=F_BODY,
            space_after=10, line_spacing=1.1, bullet_color=BLUE, marker="—"):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    for i, text in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        r1 = p.add_run(); r1.text = marker + "  "
        r1.font.size = Pt(size); r1.font.color.rgb = bullet_color; r1.font.bold = True; r1.font.name = font
        r2 = p.add_run(); r2.text = text
        r2.font.size = Pt(size); r2.font.color.rgb = color; r2.font.name = font
    return tb


_A_NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def _apply_arrowhead(conn, dashed=False):
    ln = conn.line._get_or_add_ln()
    if dashed:
        ln.append(parse_xml(f'<a:prstDash {_A_NS} val="dash"/>'))
    ln.append(parse_xml(f'<a:tailEnd {_A_NS} type="triangle" w="med" len="med"/>'))


def add_arrow(slide, x1, y1, x2, y2, color=BLUE, weight=Pt(2.0), dashed=False):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    conn.shadow.inherit = False
    conn.line.color.rgb = color
    conn.line.width = weight
    _apply_arrowhead(conn, dashed=dashed)
    return conn


def corner_brackets(slide, color=BLUE, inset=Inches(0.35), size=Inches(0.28), weight=Pt(2.25)):
    positions = [(inset, inset, 1, 1), (SLIDE_W - inset, inset, -1, 1)]
    for x, y, dx, dy in positions:
        rect(slide, x if dx > 0 else x - size, y, size, Pt(2.5), fill=color)
        rect(slide, x if dx > 0 else x - Pt(2.5), y, Pt(2.5), size, fill=color)


def status_dot(slide, cx, cy, kind="done", d=Inches(0.16)):
    colors = {"done": GREEN, "partial": AMBER, "gap": RED, "roadmap": GRAY_STATUS}
    shp = autoshape(slide, MSO_SHAPE.OVAL, cx - d // 2, cy - d // 2, d, d, fill=colors[kind])
    return shp


def footer(slide):
    PAGE_NO[0] += 1
    txt(slide, Inches(0.55), Inches(7.14), Inches(8), Inches(0.3),
        "SENTINEL  //  Gujarat Police Innovation Challenge 2026", size=8.5, color=MUTED, font=F_BODY, tracking=True)
    txt(slide, Inches(11.6), Inches(7.14), Inches(1.4), Inches(0.3),
        f"{PAGE_NO[0]:02d} / {TOTAL}", size=8.5, color=MUTED, align=PP_ALIGN.RIGHT, font=F_BODY)


def header(slide, kicker, title, title_size=32):
    rect(slide, 0, 0, SLIDE_W, Inches(1.28), fill=NAVY)
    rect(slide, 0, Inches(1.28), SLIDE_W, Pt(2.5), fill=BLUE)
    bw = Inches(0.22)
    for (bx, by, dx) in [(Inches(0.5), Inches(0.28), 1), (SLIDE_W - Inches(0.5) - bw, Inches(0.28), -1)]:
        rect(slide, bx, by, bw, Pt(2.25), fill=AMBER)
        rect(slide, bx if dx > 0 else bx + bw - Pt(2.25), by, Pt(2.25), bw, fill=AMBER)
    txt(slide, Inches(0.9), Inches(0.24), Inches(9), Inches(0.3), kicker.upper(),
        size=11.5, color=AMBER, bold=True, font=F_BODY_SB, tracking=True)
    txt(slide, Inches(0.88), Inches(0.54), Inches(11.5), Inches(0.66), title,
        size=title_size, color=WHITE, bold=True, font=F_TITLE)


def content_slide(kicker, title, title_size=32):
    s = add_slide()
    set_bg(s, WHITE)
    header(s, kicker, title, title_size)
    footer(s)
    return s


def card(slide, l, t, w, h, title, body, accent=BLUE, title_size=16, body_size=12.5):
    rrect(slide, l, t, w, h, fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.06)
    rect(slide, l, t, Pt(3.5), h, fill=accent)
    txt(slide, l + Inches(0.22), t + Inches(0.16), w - Inches(0.4), Inches(0.4), title,
        size=title_size, color=INK, bold=True, font=F_BODY_SB)
    txt(slide, l + Inches(0.22), t + Inches(0.58), w - Inches(0.4), h - Inches(0.75), body,
        size=body_size, color=MUTED, font=F_BODY, line_spacing=1.25)


def stat_block(slide, l, t, w, number, label, color=BLUE, number_size=54, label_size=13):
    txt(slide, l, t, w, Inches(0.9), number, size=number_size, color=color, bold=True, font=F_TITLE, align=PP_ALIGN.CENTER)
    txt(slide, l, t + Inches(0.85), w, Inches(0.5), label, size=label_size, color=MUTED, font=F_BODY, align=PP_ALIGN.CENTER, line_spacing=1.15)


# ============================================================ 1 — TITLE
s = add_slide(); set_bg(s, NAVY_DEEP)
for i in range(0, 14):
    rect(s, Inches(i * 1.0), 0, Pt(0.6), SLIDE_H, fill=RGBColor(0x10, 0x1A, 0x2C))
rect(s, 0, Inches(6.0), SLIDE_W, Pt(2.5), fill=BLUE)
rect(s, 0, Inches(6.0), Inches(3.2), Pt(2.5), fill=AMBER)
corner_brackets(s, color=AMBER)
txt(s, Inches(0.95), Inches(0.75), Inches(9), Inches(0.35), "GUJARAT POLICE INNOVATION CHALLENGE 2026",
    size=12.5, color=AMBER, bold=True, font=F_BODY_SB, tracking=True)
txt(s, Inches(0.88), Inches(2.15), Inches(11.5), Inches(1.7), "SENTINEL",
    size=96, color=WHITE, bold=True, font=F_TITLE)
txt(s, Inches(0.95), Inches(3.55), Inches(10.8), Inches(0.85),
    "The interoperability and accountability layer for Gujarat's existing CCTV estate",
    size=19, color=RGBColor(0xB9, 0xC6, 0xDA), line_spacing=1.3, font=F_BODY_L)
txt(s, Inches(0.95), Inches(6.22), Inches(9), Inches(0.4),
    "Solution Presentation  ·  Model 1 + 2 Hybrid  ·  Phase 1 Submission", size=12.5, color=MUTED_LT, font=F_BODY)

# ============================================================ 2 — PROBLEM
s = content_slide("The problem", "Gujarat already has cameras, VMS and ANPR, but they don't talk to each other")
cards = [
    ("Fragmented systems", "Every department runs its own VMS. A control room needs a separate viewer for each one.", BLUE),
    ("No shared evidence trail", "Sightings, ANPR reads and alerts sit in silos with no common, auditable record.", AMBER),
    ("Camera fitness unknown", "A camera can stream perfectly and never produce a usable plate read. Nobody measures it.", RED),
]
cw = Inches(3.85); gap = Inches(0.35); x0 = Inches(0.88)
for i, (t, b, c) in enumerate(cards):
    card(s, x0 + i * (cw + gap), Inches(2.3), cw, Inches(3.6), t, b, accent=c, title_size=19, body_size=14)

# ============================================================ 3 — SOLUTION MODEL
s = content_slide("Solution model", "Model 1 + 2 hybrid, mandatory. Model 3/4 as bonus scope")
rows = [
    ("Model 1: Registry & GIS", "Mandatory · Built", GREEN),
    ("Model 2: Unified Viewing", "Mandatory · Built", GREEN),
    ("Model 3: VMS Federation", "Bonus · Built", AMBER),
    ("Model 4: Central VMS", "Bonus · Pilot slice", AMBER),
]
ry = Inches(2.35)
for name, stat, c in rows:
    rrect(s, Inches(0.88), ry, Inches(11.55), Inches(0.82), fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.12)
    status_dot(s, Inches(1.25), ry + Inches(0.41), kind="done" if c == GREEN else "partial")
    txt(s, Inches(1.55), ry + Inches(0.18), Inches(7), Inches(0.5), name, size=17, color=INK, bold=True, font=F_BODY_SB)
    txt(s, Inches(9.3), ry + Inches(0.2), Inches(3), Inches(0.45), stat, size=14, color=c, bold=True, font=F_BODY_SB, align=PP_ALIGN.RIGHT)
    ry += Inches(0.98)
txt(s, Inches(0.88), Inches(6.55), Inches(11.5), Inches(0.5),
    "Departments keep full control of their own infrastructure. Sentinel adds a layer above, never a replacement.",
    size=13, color=MUTED, font=F_BODY_L, italic=True)

# ============================================================ 4 — KEY INNOVATION
s = add_slide(); set_bg(s, NAVY_DEEP)
header(s, "Key innovation", "Sentinel's contribution is refusing to let inference pass as fact", title_size=30)
footer(s)
tiers = [
    ("CONFIRMED", "Plate-supported. Only tier exportable as evidence.", GREEN, "6"),
    ("PROBABLE", "Multiple signals, needs review. Not exportable.", AMBER, "requires review"),
    ("LEAD ONLY", "Appearance/inference only. Export disabled in code.", RED, "12,251 of 12,257"),
]
cw = Inches(3.85); gap = Inches(0.35); x0 = Inches(0.88)
for i, (title, body, c, stat) in enumerate(tiers):
    x = x0 + i * (cw + gap)
    rrect(s, x, Inches(2.15), cw, Inches(3.9), fill=NAVY_CARD, line=None, radius=0.06)
    rect(s, x, Inches(2.15), cw, Pt(5), fill=c)
    txt(s, x + Inches(0.25), Inches(2.42), cw - Inches(0.5), Inches(0.5), title, size=20, color=c, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.25), Inches(2.95), cw - Inches(0.5), Inches(1.1), body, size=13, color=RGBColor(0xB9,0xC6,0xDA), font=F_BODY, line_spacing=1.3)
    txt(s, x + Inches(0.25), Inches(4.5), cw - Inches(0.5), Inches(1.2), stat, size=30 if len(stat) < 5 else 17, color=WHITE, bold=True, font=F_TITLE)
txt(s, Inches(0.88), Inches(6.35), Inches(11.5), Inches(0.6),
    "Measured on the real database. Appearance-only links score a 41.87% false-positive rate on confirmed-different vehicles, which is exactly why they stay a lead, never a fact.",
    size=12.5, color=MUTED_LT, font=F_BODY_L)

# ============================================================ 5 — ARCHITECTURE
s = content_slide("Architecture", "Existing systems keep running. Sentinel sits above them")
boxes = [
    (Inches(0.65), "Departmental\nsystems", "VMS · RTSP\nONVIF · ANPR", SURFACE, INK, LINE),
    (Inches(4.35), "Sentinel\nintegration layer", "Normalize\nvendor-neutral", NAVY, WHITE, NAVY),
    (Inches(8.05), "Registry · GIS\nViewer · Analytics", "Camera health\nWatchlist", SURFACE, INK, LINE),
]
bw, bh, by = Inches(3.1), Inches(2.9), Inches(2.55)
for x, title, sub, fill, tc, ln in boxes:
    rrect(s, x, by, bw, bh, fill=fill, line=ln, line_w=Pt(1), radius=0.06)
    txt(s, x + Inches(0.25), by + Inches(0.35), bw - Inches(0.5), Inches(0.9), title, size=18, color=tc, bold=True, font=F_BODY_SB, align=PP_ALIGN.CENTER, line_spacing=1.15)
    txt(s, x + Inches(0.25), by + Inches(1.7), bw - Inches(0.5), Inches(0.9), sub, size=13, color=tc if fill==NAVY else MUTED, font=F_BODY, align=PP_ALIGN.CENTER, line_spacing=1.25)
add_arrow(s, Inches(3.75), by + bh/2, Inches(4.35), by + bh/2, color=BLUE, weight=Pt(3))
add_arrow(s, Inches(7.45), by + bh/2, Inches(8.05), by + bh/2, color=BLUE, weight=Pt(3))
txt(s, Inches(0.88), Inches(5.85), Inches(11.5), Inches(0.9),
    "Normalized event flow: Search & timeline · Watchlist & alerts · Confidence tier · Audit & §63 evidence export.",
    size=14, color=MUTED, font=F_BODY_L)

# ============================================================ 6 — WORKFLOW
s = content_slide("End-to-end workflow", "From camera feed to auditable alert")
steps_top = ["Ingest", "Detect & track", "ANPR / attributes", "Normalize"]
steps_bot = ["Search & correlate", "Alert", "Evidence package", "Audit"]
for row_i, (steps, y) in enumerate([(steps_top, Inches(2.35)), (steps_bot, Inches(4.55))]):
    x = Inches(0.88); w = Inches(2.55); gap = Inches(0.28); h = Inches(1.7)
    for j, label in enumerate(steps):
        fill = SURFACE if row_i == 0 else RGBColor(0xEA,0xF6,0xEF)
        line = LINE if row_i == 0 else RGBColor(0xBF,0xE3,0xCD)
        rrect(s, x, y, w, h, fill=fill, line=line, line_w=Pt(0.75), radius=0.1)
        txt(s, x + Inches(0.15), y + Inches(0.6), w - Inches(0.3), Inches(0.6), f"{row_i*4+j+1}. {label}", size=14, color=INK, bold=True, font=F_BODY_SB, align=PP_ALIGN.CENTER, line_spacing=1.1)
        if j < 3:
            add_arrow(s, x + w, y + h/2, x + w + gap, y + h/2, color=BLUE, weight=Pt(2))
        x += w + gap

# ============================================================ 7 — ANPR REAL RESULT
s = add_slide(); set_bg(s, NAVY_DEEP)
header(s, "AI video analytics: real result", "A real plate read, reproduced on live sandbox footage", title_size=28)
footer(s)
txt(s, Inches(0.88), Inches(2.6), Inches(11.5), Inches(1.6), "GJ19BR3000", size=110, color=WHITE, bold=True, font=F_TITLE)
txt(s, Inches(0.9), Inches(4.35), Inches(10.5), Inches(0.6), "Camera cam06 · 6 of 6 consecutive samples · confidence 0.917–0.977",
    size=17, color=CYAN, font=F_BODY_SB)
txt(s, Inches(0.9), Inches(5.05), Inches(10.5), Inches(0.8),
    "Detection (YOLOv8), then plate localisation (YOLOv11), PaddleOCR, pattern validation, and temporal consensus. ByteTrack tracks within one camera only. It is never presented as cross-camera tracking.",
    size=13.5, color=MUTED_LT, font=F_BODY_L, line_spacing=1.3)

# ============================================================ 8 — MODEL 2
s = content_slide("Model 2: unified viewer", "Two genuinely independent systems, one viewer")
card(s, Inches(0.88), Inches(2.3), Inches(5.6), Inches(2.3), "System A: Gujarat sandbox",
     "Live RTSP/HLS, ANPR-processed. 30 real cameras across 5 departments.", accent=BLUE, title_size=18, body_size=14)
card(s, Inches(6.85), Inches(2.3), Inches(5.6), Inches(2.3), "System B: Caltrans District 3",
     "Real, independently-operated public CCTV API. Honestly labelled ‘periodic snapshot, not live video’.", accent=BLUE, title_size=18, body_size=14)
pills = ["RTSP / ONVIF / API aggregation", "9-tile configurable video wall", "Searchable movement records"]
px = Inches(0.88)
for p in pills:
    w = Inches(3.75)
    rrect(s, px, Inches(4.95), w, Inches(0.75), fill=RGBColor(0xEA,0xF6,0xEF), line=RGBColor(0xBF,0xE3,0xCD), line_w=Pt(0.75), radius=0.3)
    txt(s, px, Inches(5.16), w, Inches(0.4), p, size=13, color=INK, bold=True, font=F_BODY_SB, align=PP_ALIGN.CENTER)
    px += w + Inches(0.2)

# ============================================================ 9 — MODEL 3
s = content_slide("Model 3: VMS federation (bonus)", "A real adapter architecture and correlation engine")
c1 = ["Adapter Protocol, with two real adapters: Sentinel's own stack, NYC Open Data's public dataset",
      "Polled event bus, not Kafka, a deliberate pilot-scale decision, documented",
      "Correlation engine: 1,105 events / 3 sources / 4 correlations, verified end-to-end"]
bullets(s, Inches(0.88), Inches(2.35), Inches(11.5), Inches(2.4), c1, size=16, space_after=16, line_spacing=1.25)
rrect(s, Inches(0.88), Inches(5.1), Inches(11.55), Inches(1.5), fill=RGBColor(0xFF,0xF7,0xEC), line=RGBColor(0xF0,0xDC,0xB8), line_w=Pt(0.75), radius=0.08)
txt(s, Inches(1.15), Inches(5.3), Inches(11), Inches(1.1),
    "Honesty note: Systems A and B share zero real plates by construction. A third, clearly-labelled SYNTHETIC source proves the mechanism works. It is never presented as two live government systems exchanging real traffic.",
    size=13, color=RGBColor(0x8A,0x5A,0x1E), font=F_BODY_L, line_spacing=1.3)

# ============================================================ 10 — MODEL 4
s = content_slide("Model 4: central VMS", "A scoped pilot slice, not a statewide claim")
rows4 = [
    ("Density aggregation", "Test-verified", GREEN),
    ("Central pilot rollup", "Test-verified", GREEN),
    ("Storage-tier metadata", "Implemented, unverified", AMBER),
    ("Govt-DB query integration", "Interface built, access blocked", AMBER),
    ("Face recognition", "Deliberately excluded", RED),
    ("80,000-camera load test", "Not attempted", RED),
]
ry = Inches(2.25)
for name, stat, c in rows4:
    rrect(s, Inches(0.88), ry, Inches(11.55), Inches(0.68), fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.12)
    status_dot(s, Inches(1.22), ry + Inches(0.34), kind="done" if c==GREEN else ("partial" if c==AMBER else "gap"))
    txt(s, Inches(1.5), ry + Inches(0.13), Inches(7.5), Inches(0.45), name, size=15, color=INK, bold=True, font=F_BODY_SB)
    txt(s, Inches(9.3), ry + Inches(0.15), Inches(3), Inches(0.4), stat, size=12.5, color=c, bold=True, font=F_BODY_SB, align=PP_ALIGN.RIGHT)
    ry += Inches(0.8)

# ============================================================ 11 — EVIDENCE INTEGRITY
s = add_slide(); set_bg(s, NAVY_DEEP)
header(s, "Evidence integrity", "Provenance recorded at write time, never re-computed to look clean later", title_size=27)
footer(s)
cards3 = [
    ("SHA-256 at write", "Hashed the instant the crop is saved. A mismatch is reported, never healed."),
    ("Production stamp", "Records which detector/OCR class ran. A stub and a real model can't look the same."),
    ("Gated, purpose-bound export", "CONFIRMED only. Every export attempt is audit-logged before the file exists."),
]
cw = Inches(3.85); x0 = Inches(0.88)
for i, (t, b) in enumerate(cards3):
    x = x0 + i * (cw + Inches(0.35))
    rrect(s, x, Inches(2.3), cw, Inches(2.5), fill=NAVY_CARD, line=None, radius=0.06)
    txt(s, x + Inches(0.25), Inches(2.55), cw - Inches(0.5), Inches(0.5), t, size=17, color=CYAN, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.25), Inches(3.05), cw - Inches(0.5), Inches(1.5), b, size=13, color=RGBColor(0xB9,0xC6,0xDA), font=F_BODY, line_spacing=1.3)
txt(s, Inches(0.88), Inches(5.15), Inches(11.5), Inches(0.5),
    "Wording is always “§63-oriented”, never “court admissible”. That requires legal review this project hasn't had.",
    size=13, color=MUTED_LT, font=F_BODY_L, italic=True)

# ============================================================ 12 — SCALABILITY
s = content_slide("Scalability toward ~80,000 cameras", "Structured events at the edge, not raw video centrally")
stat_block(s, Inches(1.4), Inches(2.5), Inches(4.8), "160 Gbps", "Raw video, statewide (ruled out)", color=RED, number_size=50)
autoshape(s, MSO_SHAPE.RIGHT_ARROW, Inches(6.1), Inches(2.85), Inches(1.1), Inches(0.7), fill=BLUE)
stat_block(s, Inches(7.1), Inches(2.5), Inches(4.8), "640 Mbps", "Structured events only (Sentinel's design)", color=GREEN, number_size=50)
txt(s, Inches(0.88), Inches(4.6), Inches(11.5), Inches(1.6),
    "Edge, regional and central architecture. Projected from the ~30-camera pilot's measured per-stream cost, not a load test at 80,000-camera scale, which was deliberately not attempted this cycle.",
    size=15, color=MUTED, font=F_BODY, line_spacing=1.35)

# ============================================================ 13 — SECURITY & GOVERNANCE
s = content_slide("Security & governance", "Real controls, not a checklist")
items = [
    "Department-scoped RBAC, object-level, not role-only",
    "Purpose-bound search, required purpose + case ID, audited",
    "Credentials never reach the browser or logs",
    "SSRF-hardened ONVIF discovery",
    "Full audit trail on every search, export, edit",
    "Open, vendor-neutral event schema",
]
gw, gh = Inches(3.75), Inches(1.55)
for i, item in enumerate(items):
    col, row = i % 3, i // 3
    x = Inches(0.88) + col * (gw + Inches(0.15))
    y = Inches(2.3) + row * (gh + Inches(0.2))
    rrect(s, x, y, gw, gh, fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.08)
    txt(s, x + Inches(0.22), y + Inches(0.2), gw - Inches(0.44), gh - Inches(0.4), item, size=13.5, color=INK, bold=True, font=F_BODY_SB, line_spacing=1.25)

# ============================================================ 14 — HONEST STATUS
s = content_slide("Honest status", "What's proven, and what isn't, stated plainly")
rows_h = [
    ("Real ANPR read on live footage", "Verified", GREEN),
    ("Fleet-wide ANPR read rate", "Low, disclosed", AMBER),
    ("Cross-camera tracking", "Governance shown, not accuracy", AMBER),
    ("§63 evidence compliance", "“Oriented” only, no legal review", AMBER),
    ("80,000-camera scalability", "Projection, not a load test", AMBER),
]
ry = Inches(2.3)
for name, stat, c in rows_h:
    rrect(s, Inches(0.88), ry, Inches(11.55), Inches(0.78), fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.12)
    status_dot(s, Inches(1.25), ry + Inches(0.39), kind="done" if c==GREEN else "partial")
    txt(s, Inches(1.55), ry + Inches(0.17), Inches(7.5), Inches(0.45), name, size=15.5, color=INK, bold=True, font=F_BODY_SB)
    txt(s, Inches(8.6), ry + Inches(0.19), Inches(3.7), Inches(0.42), stat, size=13, color=c, bold=True, font=F_BODY_SB, align=PP_ALIGN.RIGHT)
    ry += Inches(0.92)

# ============================================================ 15 — IMPACT
s = add_slide(); set_bg(s, NAVY_DEEP)
header(s, "Expected operational impact", "Making existing investment measurable and trustworthy", title_size=28)
footer(s)
cards4 = [
    ("Control room", "One viewer instead of many. Real-time camera-fitness signal, not just stream status."),
    ("Investigators", "A search that states its own confidence honestly, with a provable evidence chain."),
    ("Leadership", "Interoperability without replacing existing VMS investment."),
]
cw = Inches(3.85); x0 = Inches(0.88)
for i, (t, b) in enumerate(cards4):
    x = x0 + i * (cw + Inches(0.35))
    txt(s, x, Inches(2.4), cw, Inches(0.5), t, size=18, color=CYAN, bold=True, font=F_BODY_SB)
    txt(s, x, Inches(2.95), cw, Inches(1.8), b, size=14, color=RGBColor(0xB9,0xC6,0xDA), font=F_BODY, line_spacing=1.35)

# ============================================================ 16 — TECH STACK
s = content_slide("Technology", "A pragmatic stack. Nothing here is claimed as novel")
stack = [
    ("Backend", "FastAPI · SQLAlchemy · SQLite/PostgreSQL"),
    ("Frontend", "React 19 + Vite"),
    ("Streaming", "RTSP · ONVIF · HLS proxy"),
    ("Analytics", "YOLOv8/v11 · PaddleOCR · ByteTrack"),
    ("Evidence", "SHA-256 · reportlab · §63-oriented export"),
    ("Access control", "Department-scoped RBAC · audit log"),
]
gw, gh = Inches(3.75), Inches(1.35)
for i, (title, body) in enumerate(stack):
    col, row = i % 3, i // 3
    x = Inches(0.88) + col * (gw + Inches(0.15))
    y = Inches(2.3) + row * (gh + Inches(0.2))
    rrect(s, x, y, gw, gh, fill=SURFACE, line=LINE, line_w=Pt(0.75), radius=0.08)
    txt(s, x + Inches(0.22), y + Inches(0.18), gw - Inches(0.44), Inches(0.4), title, size=15, color=BLUE, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.22), y + Inches(0.6), gw - Inches(0.44), Inches(0.65), body, size=12.5, color=MUTED, font=F_BODY, line_spacing=1.2)

# ============================================================ 17 — CLOSING
s = add_slide(); set_bg(s, NAVY_DEEP)
for i in range(0, 14):
    rect(s, Inches(i * 1.0), 0, Pt(0.6), SLIDE_H, fill=RGBColor(0x10, 0x1A, 0x2C))
rect(s, 0, Inches(5.85), SLIDE_W, Pt(2.5), fill=BLUE)
rect(s, 0, Inches(5.85), Inches(3.2), Pt(2.5), fill=AMBER)
corner_brackets(s, color=AMBER)
txt(s, Inches(0.9), Inches(1.9), Inches(11), Inches(1.1), "Thank you", size=58, color=WHITE, bold=True, font=F_TITLE)
txt(s, Inches(0.95), Inches(3.05), Inches(10.8), Inches(1.0),
    "Gujarat already has the eyes and the detectors. Sentinel makes what they see explainable, auditable, and evidence-ready.",
    size=16, color=RGBColor(0xB9, 0xC6, 0xDA), line_spacing=1.3, font=F_BODY_L)
bullets(s, Inches(0.97), Inches(4.3), Inches(10.5), Inches(1.3), [
    "HLD + Scalability Strategy submitted alongside this deck",
    "Own-feed and government-feed demo videos included",
    "Every claim on this deck traces to verified, runnable code or a stated gap",
], size=13.5, color=RGBColor(0xB9, 0xC6, 0xDA), space_after=8, bullet_color=AMBER, font=F_BODY_L)
txt(s, Inches(0.97), Inches(6.02), Inches(8), Inches(0.4), "SENTINEL // Gujarat Police Innovation Challenge 2026", size=11.5, color=MUTED_LT, font=F_BODY)

import os
out_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "assets", "Sentinel_Solution_Presentation.pptx")
out_path = os.path.abspath(out_path)
prs.save(out_path)
print(f"Saved {PAGE_NO[0]} slides to {out_path}")
