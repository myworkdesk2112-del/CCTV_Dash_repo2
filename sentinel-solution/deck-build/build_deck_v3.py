# Sentinel Solution Presentation — v3. Repositioning pass per
# docs/strategy/DECISION_REVIEW_2026-09-11.md: v2 still headlined "ANPR
# failure != tracking failure" and showed cross-camera appearance links as a
# proven capability. The review found that claim has no ground truth in the
# real database (0 plates repeat across cameras; the appearance encoder
# carrying 97.8% of cross-camera links measures at a 41.87% false-positive
# rate) and named it explicitly as one of the "5 things to STOP" claiming.
# v3 repositions Sentinel as "the accountability layer for Gujarat's existing
# CCTV estate" (Decision Review section W), replaces the old differentiator
# slide with the real, measured evidence-tier breakdown (CONFIRMED/PROBABLE/
# LEAD_ONLY), adds the built-and-tested Model 3 federation result, and
# corrects gaps/claims sections to match current honest implementation
# status. Visual system (fonts, palette, shape helpers) is unchanged from v2.
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
TOTAL = 21


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
    # CT_LineProperties requires strict child order: fill, then prstDash,
    # then round/bevel/miter, then headEnd, then tailEnd. Appending tailEnd
    # before prstDash produces schema-invalid XML that PowerPoint refuses to
    # open ("file is corrupted") even though python-pptx writes it silently.
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


def elbow(slide, x1, y1, x2, y2, color=BLUE, weight=Pt(2.0)):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.ELBOW, x1, y1, x2, y2)
    conn.shadow.inherit = False
    conn.line.color.rgb = color
    conn.line.width = weight
    _apply_arrowhead(conn)
    return conn


def corner_brackets(slide, color=BLUE, inset=Inches(0.35), size=Inches(0.28), weight=Pt(2.25)):
    """Small viewfinder-style corner marks — a restrained nod to the CCTV
    surveillance theme, used sparingly (header corners only)."""
    positions = [
        (inset, inset, 1, 1),
        (SLIDE_W - inset, inset, -1, 1),
    ]
    for x, y, dx, dy in positions:
        h1 = rect(slide, x if dx > 0 else x - size, y, size, Pt(2.5), fill=color)
        v1 = rect(slide, x if dx > 0 else x - Pt(2.5), y, Pt(2.5), size, fill=color)


def status_dot(slide, cx, cy, kind="done", d=Inches(0.16)):
    colors = {"done": GREEN, "partial": AMBER, "gap": RED, "roadmap": GRAY_STATUS}
    c = colors[kind]
    shp = autoshape(slide, MSO_SHAPE.OVAL, cx - d // 2, cy - d // 2, d, d, fill=c)
    return shp


def footer(slide, dark=False):
    PAGE_NO[0] += 1
    color = MUTED_LT if dark else MUTED
    txt(slide, Inches(0.55), Inches(7.14), Inches(8), Inches(0.3),
        "SENTINEL  //  Gujarat Police Innovation Challenge 2026", size=8.5, color=color, font=F_BODY, tracking=True)
    txt(slide, Inches(11.6), Inches(7.14), Inches(1.4), Inches(0.3),
        f"{PAGE_NO[0]:02d} / {TOTAL}", size=8.5, color=color, align=PP_ALIGN.RIGHT, font=F_BODY)


def header(slide, kicker, title, title_size=30):
    rect(slide, 0, 0, SLIDE_W, Inches(1.28), fill=NAVY)
    rect(slide, 0, Inches(1.28), SLIDE_W, Pt(2.5), fill=BLUE)
    # viewfinder corner accents on the header only
    bw, bl = Inches(0.22), Pt(3)
    for (bx, by, dx) in [(Inches(0.5), Inches(0.28), 1), (SLIDE_W - Inches(0.5) - bw, Inches(0.28), -1)]:
        rect(slide, bx, by, bw, Pt(2.25), fill=AMBER)
        rect(slide, bx if dx > 0 else bx + bw - Pt(2.25), by, Pt(2.25), bw, fill=AMBER)
    txt(slide, Inches(0.9), Inches(0.24), Inches(9), Inches(0.3), kicker.upper(),
        size=11.5, color=AMBER, bold=True, font=F_BODY_SB, tracking=True)
    txt(slide, Inches(0.88), Inches(0.54), Inches(11.5), Inches(0.66), title,
        size=title_size, color=WHITE, bold=True, font=F_TITLE)


def content_slide(kicker, title, title_size=30):
    s = add_slide()
    set_bg(s, WHITE)
    header(s, kicker, title, title_size)
    footer(s)
    return s


def node_label(slide, cx, cy, w, text, size=11.5, color=INK, font=F_BODY_SB, gap=Inches(0.14)):
    txt(slide, cx - w // 2, cy + gap, w, Inches(0.55), text, size=size, color=color,
        align=PP_ALIGN.CENTER, font=font, line_spacing=1.05, bold=False)


# ============================================================ 1 — TITLE
s = add_slide(); set_bg(s, NAVY_DEEP)
# faint scanline / grid texture using thin low-contrast lines
for i in range(0, 14):
    rect(s, Inches(i * 1.0), 0, Pt(0.6), SLIDE_H, fill=RGBColor(0x10, 0x1A, 0x2C))
rect(s, 0, Inches(6.0), SLIDE_W, Pt(2.5), fill=BLUE)
rect(s, 0, Inches(6.0), Inches(3.2), Pt(2.5), fill=AMBER)
corner_brackets(s, color=AMBER)
txt(s, Inches(0.95), Inches(0.75), Inches(6), Inches(0.35), "SENTINEL // CONTROL ROOM",
    size=12.5, color=AMBER, bold=True, font=F_BODY_SB, tracking=True)
txt(s, Inches(0.88), Inches(2.15), Inches(11.5), Inches(1.7), "SENTINEL",
    size=92, color=WHITE, bold=True, font=F_TITLE)
txt(s, Inches(0.95), Inches(3.55), Inches(10.5), Inches(0.85),
    "The accountability layer for Gujarat's existing CCTV estate —\nnot another detector, not a replacement VMS",
    size=18, color=RGBColor(0xB9, 0xC6, 0xDA), line_spacing=1.3, font=F_BODY_L)
txt(s, Inches(0.95), Inches(6.22), Inches(9), Inches(0.4),
    "Model 1 + Model 2 hybrid  —  Gujarat Police Innovation Challenge 2026, Phase 1", size=12.5, color=MUTED_LT, font=F_BODY)
txt(s, Inches(10.6), Inches(6.22), Inches(1.85), Inches(0.4), "₹51,00,000", size=12.5, color=AMBER, bold=True, align=PP_ALIGN.RIGHT, font=F_BODY_SB)

# ============================================================ 2 — AGENDA
s = content_slide("Roadmap", "Agenda")
agenda = [
    ("01", "The real problem"), ("02", "Positioning"), ("03", "Prior art & research"),
    ("04", "Model & justification"), ("05", "Solution overview"), ("06", "Architecture"),
    ("07", "AI analytics pipeline"), ("08", "Evidence tiers, measured"), ("09", "Governed cross-camera linking"),
    ("10", "Watchlist & alerts"), ("11", "Security & DPDP"), ("12", "Scalability"),
    ("13", "Test case & benefits"), ("14", "Honest gaps"),
]
cols = 2
cw, ch = Inches(5.9), Inches(0.62)
for i, (num, label) in enumerate(agenda):
    col = i % cols; row = i // cols
    x = Inches(0.6) + col * (cw + Inches(0.3))
    y = Inches(1.5) + row * (ch + Inches(0.09))
    rrect(s, x, y, cw, ch, fill=SURFACE, radius=0.14)
    rect(s, x, y, Inches(0.09), ch, fill=BLUE if i % 3 else AMBER)
    txt(s, x + Inches(0.24), y, Inches(0.75), ch, num, size=17, color=SURFACE2, bold=True, font=F_TITLE, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, x + Inches(0.95), y, Inches(4.5), ch, label, size=13, color=INK, bold=True, font=F_BODY_SB, anchor=MSO_ANCHOR.MIDDLE)

# ============================================================ 3 — PROBLEM
s = content_slide("The Real Problem", "Gujarat has the cameras and the ANPR. It's an integration and evidence problem.", title_size=22)
stats = [("7,078", "Cameras already live under\nVISWAS / NETRAM / TRINETRA"), ("3.8%", "of ANPR-detected violations\nreach enforcement — CAG 2025"), ("26", "Departments,\nindependent systems"), ("0", "Systems today that explain\nwhy a cross-camera link was made")]
cw = Inches(2.85)
for i, (num, label) in enumerate(stats):
    x = Inches(0.6) + i * (cw + Inches(0.15))
    rrect(s, x, Inches(1.7), cw, Inches(2.7), fill=NAVY)
    txt(s, x, Inches(2.05), cw, Inches(0.85), num, size=44, color=AMBER if i == 3 else BLUE, bold=True, align=PP_ALIGN.CENTER, font=F_TITLE)
    txt(s, x + Inches(0.2), Inches(3.05), cw - Inches(0.4), Inches(1.0), label, size=13, color=RGBColor(0xC7, 0xD3, 0xE3), align=PP_ALIGN.CENTER, line_spacing=1.25, font=F_BODY)
txt(s, Inches(0.6), Inches(4.85), Inches(12.1), Inches(0.4), "Mandatory live test case", size=16, color=NAVY, bold=True, font=F_BODY_SB)
chips = ["Onboard ~50 cameras", "Track a plate", "Timestamped route", "Watchlist cross-check", "Real-time alert"]
cx = Inches(0.6)
for c in chips:
    w = Inches(0.6 + 0.095 * len(c))
    rrect(s, cx, Inches(5.4), w, Inches(0.72), fill=SURFACE, line=LINE, line_w=Pt(1))
    txt(s, cx, Inches(5.4), w, Inches(0.72), c, size=13.5, color=INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=F_BODY_SB)
    cx += w + Inches(0.2)

# ============================================================ 4 — POSITIONING
s = content_slide("Positioning", "The accountability layer — not another vehicle-tracking AI")
c1 = rrect(s, Inches(0.6), Inches(1.7), Inches(5.85), Inches(3.1), fill=RGBColor(0x2A, 0x14, 0x14))
txt(s, Inches(0.95), Inches(1.98), Inches(5.2), Inches(0.4), "NOT the pitch", size=14, color=RED, bold=True, font=F_BODY_SB)
bullets(s, Inches(0.95), Inches(2.5), Inches(5.15), Inches(2.0), [
    "“An AI that tracks vehicles across cameras even when the plate is unreadable”",
    "Inventing ANPR or cross-camera tracking (already Staqu, Videonetics, Vehant, BriefCam)",
], size=13.5, color=RGBColor(0xEE, 0xC9, 0xC9), bullet_color=RED, space_after=14, line_spacing=1.2)
c2 = rrect(s, Inches(6.65), Inches(1.7), Inches(6.05), Inches(3.1), fill=RGBColor(0x0E, 0x28, 0x1C))
txt(s, Inches(7.0), Inches(1.98), Inches(5.4), Inches(0.4), "THE actual pitch", size=14, color=CYAN, bold=True, font=F_BODY_SB)
bullets(s, Inches(7.0), Inches(2.5), Inches(5.4), Inches(2.0), [
    "An open, vendor-neutral layer over VISWAS / TRINETRA / NETRAM",
    "Makes every cross-camera inference explainable, every query purpose-bound, every camera's ANPR fitness measurable",
], size=13.5, color=RGBColor(0xC9, 0xE9, 0xDE), bullet_color=CYAN, space_after=14, line_spacing=1.2)
txt(s, Inches(0.6), Inches(5.15), Inches(12.1), Inches(1.7),
    "Gujarat already runs VISWAS/NETRAM/TRINETRA at 7,000+ cameras. CAG's own 2025 audit found the "
    "gap is integration and evidentiary usability, not detection — only 3.8% of ANPR-detected "
    "violations reach enforcement. A jury with that knowledge asks “what did you invent?” — honesty "
    "about what is and isn't proven is the stronger pitch here, not a bigger tracking claim.",
    size=14, color=MUTED, line_spacing=1.35, font=F_BODY_L)

# ============================================================ 4b — PRIOR ART & RESEARCH
s = content_slide("Prior Art & Research", "We checked — competitors' real moat is certification and integration, not AI", title_size=21)
research_cards = [
    ("Gandhinagar already has an ICCC",
     "100+ Indian cities run Integrated Command & Control Centres — CCTV + sensors + GIS + CCTNS "
     "criminal-DB linkage. Gandhinagar, this event's own venue, runs one. Sentinel is positioned as a "
     "layer that feeds/sits above ICCC/TRINETRA/NETRAM — never pitched as a replacement.",
     "Source: India ICCC / Safe City research, §5"),
    ("Incumbents' moat isn't the AI",
     "Staqu, Videonetics, Vehant and Innefu already ship real ANPR/tracking. What actually gates "
     "government sales is STQC/ISO certification, live VAHAN/Sarthi/e-Challan integrations, and "
     "deployment track record — not detection accuracy.",
     "Source: Competitive Teardown, “most important finding”"),
    ("Our governance model has global precedent",
     "UK's National ANPR Service (11,000 cameras, ~50M reads/day) mandates 12-month retention and "
     "audits every query — and drew criticism when oversight was weak. Sentinel's purpose-bound audit "
     "log and enforced retention follow this precedent, not invent it.",
     "Source: UK NADC → NSAP research, §6"),
]
rcw = Inches(3.95); rx0 = Inches(0.6); rch = Inches(3.55)
for i, (title, desc, src) in enumerate(research_cards):
    x = rx0 + i * (rcw + Inches(0.15))
    rrect(s, x, Inches(1.65), rcw, rch, fill=SURFACE)
    rect(s, x, Inches(1.65), rcw, Inches(0.06), fill=BLUE)
    txt(s, x + Inches(0.25), Inches(1.85), rcw - Inches(0.5), Inches(0.65), title, size=13.5, color=INK, bold=True, line_spacing=1.1, font=F_BODY_SB)
    txt(s, x + Inches(0.25), Inches(2.55), rcw - Inches(0.5), Inches(2.1), desc, size=11, color=MUTED, line_spacing=1.28, font=F_BODY_L)
    txt(s, x + Inches(0.25), Inches(4.75), rcw - Inches(0.5), Inches(0.4), src, size=9.5, color=BLUE_DEEP, italic=True, font=F_BODY)
txt(s, Inches(0.6), Inches(5.45), Inches(12.1), Inches(1.5),
    "Conclusion, stated plainly: Sentinel's defensible wedge is an open, explainable architecture — "
    "it wins pilots, not yet procurement, until certification gates are cleared. That honesty is more "
    "credible to this jury than claiming the technology alone is the moat.",
    size=13.5, color=NAVY, bold=True, line_spacing=1.32, font=F_BODY_L)

# ============================================================ 5 — MODEL
s = content_slide("Solution Model", "Model 1 + 2 + 3 + a Model 4 pilot slice — a real hybrid, built and tested", title_size=25)
cards = [
    ("01", "Registry & GIS", "Mandatory foundation", "done"),
    ("02", "Unified Viewing", "Direct integration, ≥2 independent systems — Gujarat sandbox + Caltrans D3 public CCTV API", "done"),
    ("03", "VMS Federation", "Built & tested — Sentinel + NYC Open Data", "done"),
    ("04", "Model 4 — Pilot Slice", "Density aggregation, storage tiers, central rollup, ANPR-suitability — tested on master. Not the full statewide platform.", "partial"),
]
cw = Inches(2.9); x0 = Inches(0.6); ch = Inches(3.6)
for i, (num, title, sub, kind) in enumerate(cards):
    x = x0 + i * (cw + Inches(0.15))
    fill = NAVY if kind == "done" else SURFACE
    rrect(s, x, Inches(1.65), cw, ch, fill=fill)
    txt(s, x + Inches(0.25), Inches(1.85), Inches(1.8), Inches(0.75), num,
        size=34, color=(BLUE if kind == "done" else SURFACE2), bold=True, font=F_TITLE)
    status_dot(s, x + cw - Inches(0.35), Inches(2.0), kind=kind, d=Inches(0.2))
    txt(s, x + Inches(0.25), Inches(2.7), cw - Inches(0.5), Inches(0.6), title,
        size=15.5, color=(WHITE if kind == "done" else INK), bold=True, font=F_BODY_SB, line_spacing=1.05)
    txt(s, x + Inches(0.25), Inches(3.3), cw - Inches(0.5), Inches(1.85), sub,
        size=10.5, color=(RGBColor(0xB9, 0xC6, 0xDA) if kind == "done" else MUTED), line_spacing=1.2, font=F_BODY_L)
txt(s, Inches(0.6), Inches(5.45), Inches(12.1), Inches(1.4),
    "“Combine two or more models” is the problem statement's own definition of a hybrid — credit claimed "
    "only for what's built and verified. Model 3 federates our own data with a second, real, "
    "independently-operated public dataset (not a second Gujarat system). Model 4's density/storage-tier/"
    "central-rollup/ANPR-suitability pilot is tested on master; the full statewide central VMS (Kafka, "
    "Kubernetes, government-DB integration) remains roadmap, not built this cycle.",
    size=13, color=MUTED, line_spacing=1.3, font=F_BODY_L)

# ============================================================ 6 — SOLUTION OVERVIEW
s = content_slide("Solution Overview", "A governance layer that refuses to let inference pass as fact", title_size=24)
txt(s, Inches(0.6), Inches(1.58), Inches(12.1), Inches(0.5),
    "Four concrete controls, not a stronger tracking claim — each one enforced in code below.",
    size=15.5, color=MUTED, font=F_BODY_L)
inn = [
    ("A", "Evidence tiers, enforced", "CONFIRMED / PROBABLE / LEAD ONLY — a LEAD ONLY link can never be exported as evidence."),
    ("B", "Observed vs. inferred", "Route gaps are filled honestly — never shown as confirmed fact."),
    ("C", "Governed alerts", "Every watchlist hit is a live, attributable investigation item."),
    ("D", "“Why linked?”", "Every match shows its method and score, including when that score is weak."),
]
cw = Inches(5.95)
for i, (tag, title, desc) in enumerate(inn):
    x = Inches(0.6) + (i % 2) * (cw + Inches(0.3))
    y = Inches(2.35) + (i // 2) * Inches(2.15)
    rrect(s, x, y, cw, Inches(1.95), fill=SURFACE)
    autoshape(s, MSO_SHAPE.OVAL, x + Inches(0.28), y + Inches(0.26), Inches(0.55), Inches(0.55), fill=BLUE)
    txt(s, x + Inches(0.28), y + Inches(0.26), Inches(0.55), Inches(0.55), tag, size=17, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=F_TITLE)
    txt(s, x + Inches(1.05), y + Inches(0.22), cw - Inches(1.35), Inches(0.5), title, size=15.5, color=INK, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(1.05), y + Inches(0.72), cw - Inches(1.35), Inches(1.1), desc, size=11.5, color=MUTED, line_spacing=1.25, font=F_BODY_L)

# ============================================================ 7 — ARCHITECTURE (real diagram)
s = content_slide("Architecture", "One flow, today and at scale", title_size=27)
lane_y1, lane_y2 = Inches(1.85), Inches(4.15)
txt(s, Inches(0.6), Inches(1.62), Inches(4), Inches(0.3), "PILOT — BUILT & VERIFIED", size=11, color=GREEN, bold=True, font=F_BODY_SB)
nodes1 = [
    ("Departments", MSO_SHAPE.FLOWCHART_TERMINATOR),
    ("Catalogue", MSO_SHAPE.FLOWCHART_PROCESS),
    ("Stream\nManager", MSO_SHAPE.FLOWCHART_PROCESS),
    ("AI\nPipeline", MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS),
    ("Event\nStore", MSO_SHAPE.FLOWCHART_MAGNETIC_DISK),
    ("API +\nDashboard", MSO_SHAPE.FLOWCHART_DISPLAY),
]
n = len(nodes1)
nw, nh = Inches(1.62), Inches(1.0)
gap = (Inches(12.1) - n * nw) // (n - 1)
xs = [Inches(0.6) + i * (nw + gap) for i in range(n)]
for i, (label, shape) in enumerate(nodes1):
    x = xs[i]
    autoshape(s, shape, x, lane_y1, nw, nh, fill=NAVY, line=BLUE, line_w=Pt(1.5))
    shp = s.shapes[-1]
    shp.text_frame.word_wrap = True
    shp.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for j, seg in enumerate(label.split("\n")):
        p = shp.text_frame.paragraphs[0] if j == 0 else shp.text_frame.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = seg; r.font.size = Pt(11.5); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = F_BODY_SB
    if i < n - 1:
        add_arrow(s, x + nw, lane_y1 + nh // 2, xs[i + 1], lane_y1 + nh // 2, color=BLUE, weight=Pt(2.25))

txt(s, Inches(0.6), Inches(3.35), Inches(6.2), Inches(0.3), "PRODUCTION ROADMAP — CODE SCAFFOLDED, NOT DEPLOYED/VERIFIED", size=11, color=GRAY_STATUS, bold=True, font=F_BODY_SB)
nodes2 = [("Regional\nMedia Fabric", MSO_SHAPE.CLOUD), ("Kafka\nEvent Bus", MSO_SHAPE.CLOUD), ("Govt DBs\n(query, don't copy)", MSO_SHAPE.CLOUD), ("Governance\nPlane", MSO_SHAPE.CLOUD)]
n2 = len(nodes2)
nw2, nh2 = Inches(2.7), Inches(1.0)
gap2 = (Inches(12.1) - n2 * nw2) // (n2 - 1)
xs2 = [Inches(0.6) + i * (nw2 + gap2) for i in range(n2)]
for i, (label, shape) in enumerate(nodes2):
    x = xs2[i]
    autoshape(s, shape, x, lane_y2, nw2, nh2, fill=SURFACE, line=LINE, line_w=Pt(1.25))
    shp = s.shapes[-1]
    shp.text_frame.word_wrap = True
    shp.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for j, seg in enumerate(label.split("\n")):
        p = shp.text_frame.paragraphs[0] if j == 0 else shp.text_frame.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = seg; r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = MUTED; r.font.name = F_BODY_SB
    if i < n2 - 1:
        add_arrow(s, x + nw2, lane_y2 + nh2 // 2, xs2[i + 1], lane_y2 + nh2 // 2, color=GRAY_STATUS, weight=Pt(1.5), dashed=True)
add_arrow(s, Inches(2.0), lane_y1 + nh + Pt(4), Inches(2.0), lane_y2 - Pt(4), color=GRAY_STATUS, weight=Pt(1.25), dashed=True)
txt(s, Inches(0.6), Inches(5.2), Inches(12.1), Inches(0.28),
    "A scoped Model 4 pilot slice — density aggregation, storage tiers, central rollup, ANPR-suitability score — is already tested on master, not this diagram's full regional/central build-out.",
    size=10.5, color=GREEN, italic=True, font=F_BODY_L)
txt(s, Inches(0.6), Inches(5.6), Inches(12.1), Inches(1.2),
    "Core principle: centralize metadata, events, identity, and governance — not every raw video frame.\n"
    "80,000 cameras of raw video ≈ 160 Gbps sustained. Structured events instead ≈ 640 Mbps.",
    size=13.5, color=MUTED, line_spacing=1.35, italic=True, font=F_BODY_L)

# ============================================================ 8 — INTEGRATION
s = content_slide("Integration", "Built to the sandbox's own rulebook")
items = [
    ("TCP-forced RTSP", "Never UDP — avoids corrupt frames across NAT/firewalls"),
    ("PTS-driven timing", "CAP_PROP_FPS is never trusted for velocity/dwell math"),
    ("Backoff reconnect", "2s → 30s cap, never a tight retry loop"),
    ("Discontinuity-aware", "Recording loop points reset tracker state, not corrupt it"),
    ("Catalogue-only discovery", "No hardcoded camera URLs — IDs can change"),
    ("ONVIF-targeted", "Vendor-neutral standard for real heterogeneous cameras"),
    ("One clock authority", "Cross-camera timing never assumes NTP-synced legacy cameras"),
    ("Department tagging", "Bulk, manual, and API onboarding, protocol-independent"),
]
cw, ch = Inches(2.93), Inches(2.5)
for i, (title, desc) in enumerate(items):
    col = i % 4; row = i // 4
    x = Inches(0.6) + col * (cw + Inches(0.13))
    y = Inches(1.7) + row * (ch + Inches(0.2))
    rrect(s, x, y, cw, ch, fill=SURFACE)
    rect(s, x, y, cw, Inches(0.07), fill=BLUE)
    txt(s, x + Inches(0.2), y + Inches(0.32), cw - Inches(0.4), Inches(0.7), title, size=14, color=INK, bold=True, font=F_BODY_SB, line_spacing=1.1)
    txt(s, x + Inches(0.2), y + Inches(1.08), cw - Inches(0.4), Inches(1.3), desc, size=11, color=MUTED, line_spacing=1.25, font=F_BODY_L)

# ============================================================ 9 — AI PIPELINE (real diagram)
s = content_slide("AI Video Analytics", "Plate-first, appearance-second, geo-gated — never one black-box Re-ID model", title_size=21)
stages = [
    ("Detect", "YOLOv8n", "done"), ("Locate\nplate", "YOLOv11 (trained)", "done"), ("Enhance", "CLAHE", "done"),
    ("OCR", "PaddleOCR", "done"), ("Track", "ByteTrack", "done"), ("Re-ID", "Colour hist.", "partial"), ("Identity", "Plate-first", "done"),
]
n = len(stages)
nw, nh = Inches(1.58), Inches(1.15)
gap = (Inches(12.1) - n * nw) // (n - 1)
xs = [Inches(0.6) + i * (nw + gap) for i in range(n)]
y = Inches(2.0)
colors = {"done": GREEN, "partial": AMBER, "gap": RED}
for i, (label, sub, kind) in enumerate(stages):
    x = xs[i]
    autoshape(s, MSO_SHAPE.OVAL, x + nw // 2 - Inches(0.6), y, Inches(1.2), Inches(1.2), fill=NAVY, line=colors[kind], line_w=Pt(2.25))
    shp = s.shapes[-1]
    shp.text_frame.word_wrap = True; shp.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    shp.text_frame.margin_left = shp.text_frame.margin_right = Pt(2)
    shp.text_frame.margin_top = shp.text_frame.margin_bottom = Pt(1)
    for j, seg in enumerate(label.split("\n")):
        p = shp.text_frame.paragraphs[0] if j == 0 else shp.text_frame.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = seg; r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = F_BODY_SB
    txt(s, x, y + Inches(1.32), nw, Inches(0.35), sub, size=10, color=MUTED, align=PP_ALIGN.CENTER, font=F_BODY_L)
    if i < n - 1:
        add_arrow(s, x + nw // 2 + Inches(0.6), y + Inches(0.6), xs[i + 1] + nw // 2 - Inches(0.6), y + Inches(0.6), color=BLUE, weight=Pt(2))
legend_x = Inches(0.6)
for label, kind in [("Verified", "done"), ("Partial", "partial")]:
    status_dot(s, legend_x + Inches(0.08), Inches(3.85), kind=kind, d=Inches(0.16))
    txt(s, legend_x + Inches(0.25), Inches(3.73), Inches(1.3), Inches(0.3), label, size=11, color=MUTED, font=F_BODY_L)
    legend_x += Inches(1.5)
txt(s, Inches(0.6), Inches(4.26), Inches(12.1), Inches(0.28), "Also captured per sighting: colour, type, dimensions, dwell/speed/direction",
    size=12.5, color=INK, font=F_BODY_SB)

mech_cards = [
    ("1", "Consensus-vote plate fusion",
     "Position-weighted character vote across every frame's OCR read, not exact-string majority — one "
     "misread character can't outvote an otherwise-agreeing plate. Real case: cam06, 4/5 frames agree, "
     "0.81 confidence."),
    ("2", "Hard geo-feasibility gate",
     "An appearance-only cross-camera match is accepted only if it also clears a physical feasibility "
     "check — haversine distance ÷ elapsed time vs. a plausible max speed. Infeasible candidates are "
     "excluded outright, not just down-scored."),
]
mcw = Inches(5.95); mch = Inches(1.12); mx0 = Inches(0.6); my0 = Inches(4.6)
for i, (tag, title, desc) in enumerate(mech_cards):
    x = mx0 + i * (mcw + Inches(0.2))
    rrect(s, x, my0, mcw, mch, fill=SURFACE)
    rect(s, x, my0, Inches(0.08), mch, fill=BLUE)
    autoshape(s, MSO_SHAPE.OVAL, x + Inches(0.26), my0 + Inches(0.18), Inches(0.42), Inches(0.42), fill=NAVY)
    txt(s, x + Inches(0.26), my0 + Inches(0.18), Inches(0.42), Inches(0.42), tag, size=15, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=F_TITLE)
    txt(s, x + Inches(0.85), my0 + Inches(0.13), mcw - Inches(1.1), Inches(0.32), title, size=13, color=INK, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.85), my0 + Inches(0.46), mcw - Inches(1.1), Inches(0.62), desc, size=10, color=MUTED, line_spacing=1.15, font=F_BODY_L)

txt(s, Inches(0.6), Inches(5.86), Inches(12.1), Inches(0.28), "Not built: make/model classification — no open-source Indian-market model exists; stated, not faked.",
    size=11.5, color=MUTED, italic=True, font=F_BODY_L)
txt(s, Inches(0.6), Inches(6.18), Inches(12.1), Inches(0.85),
    "Real-footage result: a real sandbox vehicle's plate (GJ19BR3000) read correctly 6/6 times on "
    "camera cam06, verified through the actual production accept-logic. A single-camera read, stated as "
    "exactly that — not evidence of cross-camera tracking.",
    size=12.5, color=GREEN, bold=True, line_spacing=1.25, font=F_BODY_L)

# ============================================================ 10 — EVIDENCE TIERS
s = content_slide("Evidence Tiers", "We measured our own weakest link — and refuse to hide it")
tiers3 = [
    ("CONFIRMED", "6", "of 12,257 events", "This sighting read and validated its own plate.", GREEN),
    ("PROBABLE", "4", "plate_upgrade links", "No plate here, but linked by within-camera track continuity from one that read.", AMBER),
    ("LEAD ONLY", "12,251", "appearance-only or anonymous", "41.87% measured false-positive rate. Not exportable as evidence.", RED),
]
cw = Inches(3.85); x0c = Inches(0.6)
for i, (name, num, sub, desc, c) in enumerate(tiers3):
    x = x0c + i * (cw + Inches(0.2))
    rrect(s, x, Inches(1.72), cw, Inches(2.85), fill=NAVY, line=c, line_w=Pt(1.75))
    txt(s, x + Inches(0.28), Inches(1.92), cw - Inches(0.56), Inches(0.35), name, size=14.5, color=c, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.28), Inches(2.28), cw - Inches(0.56), Inches(0.75), num, size=34, color=WHITE, bold=True, font=F_TITLE)
    txt(s, x + Inches(0.28), Inches(3.0), cw - Inches(0.56), Inches(0.35), sub, size=11, color=MUTED_LT, font=F_BODY_L)
    txt(s, x + Inches(0.28), Inches(3.42), cw - Inches(0.56), Inches(1.05), desc, size=11.5, color=RGBColor(0xC7, 0xD3, 0xE3), line_spacing=1.25, font=F_BODY_L)
txt(s, Inches(0.6), Inches(4.85), Inches(12.1), Inches(0.4), "Only CONFIRMED is exportable. PROBABLE is deliberately excluded too — an export is where a hedge stops being visible.",
    size=13.5, color=NAVY, bold=True, font=F_BODY_SB)
txt(s, Inches(0.6), Inches(5.4), Inches(12.1), Inches(1.4),
    "Real query over the live sentinel.db, not a projection. The appearance encoder carrying 97.8% of "
    "cross-camera links is a colour-histogram model we ourselves measured at a 41.87% false-positive rate "
    "on real confirmed-different-vehicle pairs — so the system labels that class LEAD ONLY and blocks its "
    "export, rather than presenting it as a tracked vehicle.",
    size=13.5, color=INK, line_spacing=1.35, font=F_BODY_L)

# ============================================================ 11 — GEO-TEMPORAL
s = content_slide("Governed Cross-Camera Linking", "Observed vs. inferred — never conflated")
pts = [("cam01", "OBSERVED", "done"), ("inferred", "plausible", "roadmap"), ("cam03", "OBSERVED", "done"), ("inferred", "not direct — flagged", "gap"), ("cam05", "OBSERVED", "done")]
seg_w = Inches(2.35); start_x = Inches(0.65); ty = Inches(2.0)
for i, (label, sub, kind) in enumerate(pts):
    x = start_x + i * seg_w
    if kind == "done":
        rrect(s, x, ty, Inches(1.85), Inches(1.15), fill=NAVY)
        status_dot(s, x + Inches(0.35), ty + Inches(0.32), kind="done", d=Inches(0.16))
        txt(s, x + Inches(0.15), ty + Inches(0.2), Inches(1.55), Inches(0.35), label, size=15, color=WHITE, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
        txt(s, x, ty + Inches(0.68), Inches(1.85), Inches(0.35), sub, size=10.5, color=CYAN, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_L)
    else:
        c = AMBER if kind == "roadmap" else RED
        rrect(s, x, ty + Inches(0.18), Inches(1.85), Inches(0.8), fill=SURFACE, line=c, line_w=Pt(1.5))
        txt(s, x, ty + Inches(0.26), Inches(1.85), Inches(0.3), "INFERRED", size=11, color=c, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
        txt(s, x + Inches(0.1), ty + Inches(0.56), Inches(1.65), Inches(0.35), sub, size=9.5, color=MUTED, align=PP_ALIGN.CENTER, font=F_BODY_L, line_spacing=1.0)
    if i < len(pts) - 1:
        add_arrow(s, x + Inches(1.87), ty + Inches(0.58), x + seg_w - Inches(0.03), ty + Inches(0.58), color=MUTED_LT, weight=Pt(1.5))
txt(s, Inches(0.6), Inches(3.55), Inches(12.1), Inches(0.9),
    "Straight-line distance + time-gap feasibility between sightings — a lead, never presented as fact. "
    "A high implied speed flags “not a direct drive.” Appearance-only links carry the same discipline: "
    "labelled LEAD ONLY, shown with their score, and never silently upgraded to CONFIRMED.",
    size=13.5, color=MUTED, line_spacing=1.3, font=F_BODY_L)
txt(s, Inches(0.6), Inches(4.7), Inches(12.1), Inches(0.4), "Deliberately roadmap, not built:", size=14, color=NAVY, bold=True, font=F_BODY_SB)
bullets(s, Inches(0.6), Inches(5.15), Inches(12.1), Inches(1.2), [
    "Road-network (OSM) routing — Gujarat's minor-road coverage is incomplete",
    "Predictive next-camera pruning — 80k-scale value, not observable at a 50-camera pilot",
], size=13, space_after=8, color=MUTED, bullet_color=AMBER, font=F_BODY_L)

# ============================================================ 12 — WATCHLIST LIFECYCLE
s = content_slide("Watchlist Correlation", "A lead, not a verdict")
states = ["NEW", "ACKNOWLEDGED", "RESOLVED"]
sx = Inches(0.85); sw = Inches(2.5); sy = Inches(1.85)
for i, st in enumerate(states):
    x = sx + i * (sw + Inches(0.6))
    fill = NAVY if i == 0 else (SURFACE if i == 1 else RGBColor(0x0E, 0x28, 0x1C))
    rrect(s, x, sy, sw, Inches(0.85), fill=fill)
    txt(s, x, sy + Inches(0.27), sw, Inches(0.35), st, size=15, color=(WHITE if i != 1 else INK), bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
    if i < 2:
        add_arrow(s, x + sw, sy + Inches(0.42), x + sw + Inches(0.55), sy + Inches(0.42), color=BLUE, weight=Pt(2.25))
dx = sx + sw + Inches(0.6)
rrect(s, dx, sy + Inches(1.3), sw, Inches(0.85), fill=RGBColor(0x2A, 0x14, 0x14), line=RED, line_w=Pt(1.25))
txt(s, dx, sy + Inches(1.58), sw, Inches(0.35), "DISMISSED", size=14, color=RED, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
add_arrow(s, sx + Inches(0.2), sy + Inches(0.85), dx + Inches(0.2), sy + Inches(1.3), color=RED, weight=Pt(1.5), dashed=True)

txt(s, Inches(0.6), Inches(3.95), Inches(5.9), Inches(0.4), "How it works", size=15, color=NAVY, bold=True, font=F_BODY_SB)
bullets(s, Inches(0.6), Inches(4.4), Inches(5.9), Inches(2.2), [
    "Watchlist match → alert, instantly",
    "Only server-declared transitions are legal",
    "Every move records who, and when",
], size=13.5, space_after=12, font=F_BODY_L)
txt(s, Inches(6.85), Inches(3.95), Inches(5.85), Inches(0.4), "“Why was this linked?”", size=15, color=NAVY, bold=True, font=F_BODY_SB)
bullets(s, Inches(6.85), Inches(4.4), Inches(5.85), Inches(2.2), [
    "Plate 50% / appearance 35% / recency 15%",
    "A transparency aid, not a calibrated probability",
    "Low-confidence links are never equal-weighted with a confirmed hit",
], size=13.5, space_after=12, font=F_BODY_L)

# ============================================================ 13 — SECURITY
s = content_slide("Governance", "RBAC and retention enforced in code — not policy-on-paper", title_size=24)
items = [
    ("Real RBAC", "Genuine 401/403 — not decoration"),
    ("Purpose-bound audit", "Every query logs user, purpose, case"),
    # Added 2026-09-19 — both are real code, see analytics/evidence_integrity.py
    # and api/routes_evidence.py (27 tests). Kept to what is actually
    # enforced: "verified on export" would overclaim, since the hash is
    # RECOMPUTED and compared at export, and a mismatch is surfaced rather
    # than blocking — the claim is detection, not prevention.
    ("Evidence hash-at-write", "SHA-256 at capture — a later edit shows as a mismatch"),
    ("§63-oriented export", "Provenance + Part A/B form, CONFIRMED tier only"),
    ("No face recognition", "Deliberate — DPDP risk + documented bias"),
    ("Data minimization", "No face embeddings, anywhere"),
    ("Enforced retention", "Purges in code, not policy-on-paper"),
    ("Found & fixed", "SSRF gap closed during development"),
]
# 4x2 rather than 3x2: the two evidence-integrity controls above are real
# now, and a 7-card 3x3 grid would leave two dead slots.
cw, ch = Inches(2.93), Inches(2.15)
for i, (title, desc) in enumerate(items):
    col = i % 4; row = i // 4
    x = Inches(0.6) + col * (cw + Inches(0.13))
    y = Inches(1.7) + row * (ch + Inches(0.2))
    rrect(s, x, y, cw, ch, fill=SURFACE)
    autoshape(s, MSO_SHAPE.OVAL, x + Inches(0.25), y + Inches(0.26), Inches(0.42), Inches(0.42), fill=BLUE)
    # Title BELOW the icon, not beside it: at this narrower card width a
    # side-by-side title only gets ~1.7in and wraps mid-phrase.
    txt(s, x + Inches(0.25), y + Inches(0.82), cw - Inches(0.5), Inches(0.5), title, size=13.5, color=INK, bold=True, font=F_BODY_SB, line_spacing=1.1)
    txt(s, x + Inches(0.25), y + Inches(1.35), cw - Inches(0.5), Inches(0.72), desc, size=10.5, color=MUTED, line_spacing=1.2, font=F_BODY_L)
txt(s, Inches(0.6), Inches(6.35), Inches(12.1), Inches(0.4),
    "DPDP §17 exempts law-enforcement processing — designed as if the Act's substantive obligations apply anyway.",
    size=13, color=MUTED, italic=True, font=F_BODY_L)

# ============================================================ 14 — TECH STACK
s = content_slide("Technology", "Open source, end to end — meets the hackathon's requirement in full", title_size=23)
groups = [
    ("Backend & data", ["FastAPI", "SQLAlchemy", "PostgreSQL / PostGIS"]),
    ("Computer vision", ["OpenCV", "YOLOv8", "PaddleOCR", "ByteTrack"]),
    ("Frontend", ["React", "Leaflet", "hls.js"]),
    ("Roadmap", ["Kafka", "MediaMTX", "pgvector / Milvus"]),
]
cw = Inches(2.93)
for i, (grp, tools) in enumerate(groups):
    x = Inches(0.6) + i * (cw + Inches(0.13))
    dim = i == 3
    rrect(s, x, Inches(1.65), cw, Inches(4.4), fill=(SURFACE if not dim else WHITE), line=(LINE if dim else None))
    rect(s, x, Inches(1.65), cw, Inches(0.55), fill=(BLUE_DEEP if not dim else GRAY_STATUS))
    txt(s, x, Inches(1.79), cw, Inches(0.3), grp, size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
    y = Inches(2.45)
    for t in tools:
        rrect(s, x + Inches(0.2), y, cw - Inches(0.4), Inches(0.55), fill=(WHITE if not dim else SURFACE), line=LINE, line_w=Pt(1))
        txt(s, x + Inches(0.2), y, cw - Inches(0.4), Inches(0.55), t, size=12.5, color=(INK if not dim else MUTED), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=F_BODY_SB)
        y += Inches(0.68)
txt(s, Inches(0.6), Inches(6.35), Inches(12.1), Inches(0.4), "No proprietary/closed-source component anywhere in the analytics or serving path.", size=13, color=MUTED, italic=True, font=F_BODY_L)

# ============================================================ 15 — SCALABILITY
s = content_slide("Scalability", "Same codebase, four phased tiers — pilot to statewide, no rewrite", title_size=23)
stats2 = [("~4,000", "GPU-class edge units\nat full build-out"), ("640 Mbps", "Structured events —\nnot 160 Gbps raw video"), ("3", "Storage tiers:\nhot / warm / cold"), ("4", "Phased rollout stages,\nsame codebase")]
cw = Inches(2.85)
for i, (num, label) in enumerate(stats2):
    x = Inches(0.6) + i * (cw + Inches(0.15))
    rrect(s, x, Inches(1.65), cw, Inches(1.85), fill=NAVY)
    txt(s, x, Inches(1.87), cw, Inches(0.75), num, size=32, color=(AMBER if i == 1 else BLUE), bold=True, align=PP_ALIGN.CENTER, font=F_TITLE)
    txt(s, x + Inches(0.15), Inches(2.6), cw - Inches(0.3), Inches(0.8), label, size=11.5, color=RGBColor(0xC7, 0xD3, 0xE3), align=PP_ALIGN.CENTER, line_spacing=1.15, font=F_BODY_L)
tiers = [("Edge", "RTSP + inference"), ("Regional", "Re-ID, media relay — NETRAM-aligned"), ("Central", "Identity correlation, watchlist, RBAC")]
tw = Inches(3.95)
for i, (t, d) in enumerate(tiers):
    x = Inches(0.6) + i * (tw + Inches(0.15))
    rrect(s, x, Inches(3.8), tw, Inches(1.3), fill=SURFACE)
    txt(s, x + Inches(0.25), Inches(3.98), tw - Inches(0.5), Inches(0.4), t, size=14.5, color=BLUE_DEEP, bold=True, font=F_BODY_SB)
    txt(s, x + Inches(0.25), Inches(4.4), tw - Inches(0.5), Inches(0.6), d, size=11.5, color=MUTED, line_spacing=1.2, font=F_BODY_L)
    if i < 2:
        add_arrow(s, x + tw, Inches(4.45), x + tw + Inches(0.15), Inches(4.45), color=BLUE, weight=Pt(2))
txt(s, Inches(0.6), Inches(5.5), Inches(12.1), Inches(0.9),
    "Same codebase at every phase — pilot, district, regional, statewide. The 80,000-camera figures above "
    "are arithmetic projections from the ~30-camera pilot's measured per-stream cost, not a proven statewide result.",
    size=13, color=MUTED, italic=True, line_spacing=1.3, font=F_BODY_L)

# ============================================================ 16 — TEST CASE STATUS
s = content_slide("Evaluation Readiness", "7 of 9 live test-case items done end-to-end on the real sandbox", title_size=23)
rows2 = [
    ("Onboard ~50 cameras", "done"), ("Track by plate", "done"), ("Timestamped route", "done"),
    ("Watchlist cross-check", "done"), ("Real-time alert", "done"), ("Continuity w/o plate (LEAD ONLY)", "partial"),
    # §63 export moved gap -> partial 2026-09-19: hash-at-write, the
    # provenance package and the PDF certificate are built and covered by
    # 27 tests, but none of it has been run against the real accumulated
    # pilot DB and there is no UI control yet — "done end-to-end on the
    # real sandbox" (this slide's own headline) would overclaim it.
    ("Real-footage OCR accuracy", "done"), ("§63-oriented evidence export", "partial"), ("Camera ANPR-suitability score", "done"),
]
cw, ch = Inches(3.93), Inches(1.2)
for i, (label, kind) in enumerate(rows2):
    col = i % 3; row = i // 3
    x = Inches(0.6) + col * (cw + Inches(0.15))
    y = Inches(1.7) + row * (ch + Inches(0.2))
    rrect(s, x, y, cw, ch, fill=SURFACE)
    status_dot(s, x + Inches(0.4), y + ch // 2, kind=kind, d=Inches(0.22))
    txt(s, x + Inches(0.7), y, cw - Inches(0.9), ch, label, size=14, color=INK, bold=True, anchor=MSO_ANCHOR.MIDDLE, font=F_BODY_SB, line_spacing=1.15)
txt(s, Inches(0.6), Inches(6.35), Inches(12.1), Inches(0.4),
    "Sandbox connectivity fixed & confirmed 2026-09-04 — all 30 real cameras reachable end-to-end.",
    size=14, color=GREEN, bold=True, font=F_BODY_SB)

# ============================================================ 17 — OPERATIONAL BENEFITS
s = content_slide("Operational Benefits", "Every stakeholder gets less guesswork, not more dashboards", title_size=24)
groups2 = [
    ("Investigators", ["One search, even with bad reads", "See why a link was made, and how weak", "Provenance package for legal review — §63-oriented"]),
    ("Command", ["Live GIS + gap analysis", "Auditable alert lifecycle", "Cross-camera route patterns"]),
    ("Governance", ["Retention enforced in code", "Hashed credentials", "No face recognition, by design"]),
]
cw = Inches(3.95)
for i, (grp, items) in enumerate(groups2):
    x = Inches(0.6) + i * (cw + Inches(0.15))
    rrect(s, x, Inches(1.65), cw, Inches(4.7), fill=SURFACE)
    rect(s, x, Inches(1.65), cw, Inches(0.6), fill=BLUE_DEEP)
    txt(s, x, Inches(1.8), cw, Inches(0.35), grp, size=15, color=WHITE, bold=True, align=PP_ALIGN.CENTER, font=F_BODY_SB)
    bullets(s, x + Inches(0.3), Inches(2.65), cw - Inches(0.6), Inches(3.5), items, size=14.5, space_after=42, line_spacing=1.3, font=F_BODY_L)

# ============================================================ 18 — HONEST GAPS
s = content_slide("Honest Gaps", "Stated, not hidden — by design")
gaps = [
    "§63 export — built & tested, no UI control or legal review yet",
    "Face recognition — deliberate exclusion", "Full 80k-camera physical ingestion",
    "Live ONVIF device validated — mocked-tests only", "WHEP low-latency preview",
    "Appearance-Re-ID accuracy — measured, not fixed", "Road-network routing & pruning",
]
cw, ch = Inches(5.95), Inches(0.95)
for i, g in enumerate(gaps):
    col = i % 2; row = i // 2
    x = Inches(0.6) + col * (cw + Inches(0.2))
    y = Inches(1.65) + row * (ch + Inches(0.13))
    rrect(s, x, y, cw, ch, fill=SURFACE)
    rect(s, x, y, Inches(0.09), ch, fill=AMBER)
    txt(s, x + Inches(0.32), y, cw - Inches(0.55), ch, g, size=13.5, color=INK, anchor=MSO_ANCHOR.MIDDLE, font=F_BODY, line_spacing=1.15)

# ============================================================ 18b — REFERENCES
s = content_slide("References", "Sources behind the claims in this deck")
refs = [
    ("Gujarat Police Sentinel — official problem statement", "sentinel.gujarat.gov.in"),
    ("Only 3.8% of ANPR-detected violations reach enforcement", "CAG audit, 2025"),
    ("Appearance-link false-positive rate (41.87%), measured on real sandbox data", "calibrate_embedding_threshold.py, project test"),
    ("VISWAS / NETRAM / TRINETRA scale (7,000+ cameras, 34 district centres)", "Gujarat Home Dept. public statements"),
    ("Commercial ANPR/tracking precedent", "Staqu JARVIS, Videonetics, Vehant, Innefu"),
    ("Field ANPR accuracy vs. lab benchmarks (71% misread rate cited)", "Business Insider / Gizmodo, Aug 2026; Davis Vanguard, Aug 2026"),
    ("Indian-traffic detector benchmark, evaluated not integrated", "IISc AI for Integrated Mobility — UVH-26, arXiv 2511.02563"),
    ("Data-protection design posture", "Digital Personal Data Protection Act, 2023 — Section 17"),
    ("UK National ANPR retention precedent", "cited in RESEARCH_EXISTING_SYSTEMS.md §6"),
]
cols_ref = [refs[:3], refs[3:6], refs[6:]]
col_w = Inches(3.93)
row_h = Inches(1.32)
row_gap = Inches(0.18)
y0 = Inches(1.7)
for c, col_items in enumerate(cols_ref):
    x = Inches(0.6) + c * (col_w + Inches(0.15))
    y = y0
    for title, src in col_items:
        rrect(s, x, y, col_w, row_h, fill=SURFACE)
        rect(s, x, y, Inches(0.07), row_h, fill=BLUE)
        txt(s, x + Inches(0.28), y + Inches(0.18), col_w - Inches(0.5), Inches(0.9), title,
            size=13, color=INK, bold=True, font=F_BODY_SB, line_spacing=1.15)
        txt(s, x + Inches(0.28), y + row_h - Inches(0.42), col_w - Inches(0.5), Inches(0.32), src,
            size=10.5, color=MUTED, italic=True, font=F_BODY_L)
        y += row_h + row_gap

txt(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.32),
    "Full citation detail and dated URLs: sentinel-solution/HLD.md and RESEARCH_EXISTING_SYSTEMS.md.",
    size=11, color=MUTED, italic=True, font=F_BODY_L)

# ============================================================ 19 — CLOSING
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
    "Own-feed demo video per §9.3, real sandbox footage",
    "Every claim on this deck traces to verified, runnable code or a stated gap",
], size=13.5, color=RGBColor(0xB9, 0xC6, 0xDA), space_after=8, bullet_color=AMBER, font=F_BODY_L)
txt(s, Inches(0.97), Inches(6.02), Inches(8), Inches(0.4), "SENTINEL // Gujarat Police Innovation Challenge 2026", size=11.5, color=MUTED_LT, font=F_BODY)

import os
out_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "assets",
                         "Sentinel_Solution_Presentation.pptx")
out_path = os.path.abspath(out_path)
prs.save(out_path)
print(f"Saved {PAGE_NO[0]} slides to {out_path}")
