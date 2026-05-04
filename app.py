import streamlit as st
import streamlit.components.v1 as components
import json
import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="BIR Form 2307 Generator",
    page_icon=None,
    layout="centered",
)

# ── Custom CSS to match Pixelens branding ─────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif !important;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(102,215,115,0.18) 0, transparent 34%),
        linear-gradient(135deg, #ffffff 0%, #f9f9f9 48%, #eef6ef 100%) !important;
    border-top: 6px solid #58c066;
}

h1 {
    letter-spacing: -0.04em !important;
    color: #231f20 !important;
}

.stMainBlockContainer h1::after {
    content: "";
    display: block;
    width: 96px;
    height: 6px;
    margin-top: 14px;
    border-radius: 999px;
    background: linear-gradient(90deg, #58c066, #66d773);
}

.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 16px !important;
    border: 1px solid #cccccc !important;
    font-family: 'Inter', sans-serif !important;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #58c066 !important;
    box-shadow: 0 0 0 4px rgba(88,192,102,0.20) !important;
}

.stTextInput label, .stNumberInput label, .stSelectbox label {
    color: #136b0e !important;
    font-weight: 800 !important;
    font-size: 13px !important;
    letter-spacing: 0.02em;
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #58c066, #136b0e) !important;
    border: none !important;
    border-radius: 999px !important;
    color: #ffffff !important;
    font-weight: 800 !important;
    box-shadow: 0 12px 28px rgba(19,107,14,0.22) !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, #66d773, #58c066) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 16px 34px rgba(19,107,14,0.28) !important;
}

.stDownloadButton > button {
    background: linear-gradient(135deg, #58c066, #136b0e) !important;
    border: none !important;
    border-radius: 999px !important;
    color: white !important;
    font-weight: 800 !important;
    box-shadow: 0 12px 28px rgba(19,107,14,0.22) !important;
}

.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #66d773, #58c066) !important;
    transform: translateY(-1px) !important;
}

.streamlit-expanderHeader {
    color: #136b0e !important;
    font-weight: 800 !important;
}

[data-testid="stExpander"] {
    border: 1px solid rgba(88,192,102,0.28) !important;
    border-radius: 20px !important;
    background: linear-gradient(135deg, #ffffff 0%, #f2faf3 100%) !important;
}

[data-testid="stMetricValue"] {
    color: #136b0e !important;
}

.stAlert {
    border-radius: 16px !important;
}

hr {
    border-color: #cccccc !important;
}

.stRadio label {
    color: #231f20 !important;
    font-weight: 400 !important;
    font-size: 15px !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    color: #808080 !important;
}

/* Hide toolbar, deploy button, and manage app */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,
footer,
header[data-testid="stHeader"] .stDeployButton,
.stDeployButton,
[data-testid="manage-app-button"] {
    display: none !important;
    visibility: hidden !important;
}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# ── PDF layout constants ──────────────────────────────────────────────
PAGE_W = 612
PAGE_H = 936  # legal-ish size from the template

FONT      = "Helvetica"
FONT_SIZE = 7

# Payor is always Pixelens
PAYOR = {
    "name":    "PIXELENS CREATIVE ADVERTISING INC.",
    "tin":     "619-447-904-000",
    "address": "G8-4 2ND FLOOR GEMS PLAZA CIRCUMFERENTIAL ROAD SAN JOSE (POB.) CITY OF ANTIPOLO RIZAL",
    "zip":     "1870",
}

TAX_RATE = 0.02   # 2 % expanded withholding tax

CORP_KEYWORDS = ["INCORPORATED", "INC.", "INC", "CORP.", "CORP", "CORPORATION"]

def get_atc(supplier_name: str) -> str:
    upper = supplier_name.upper()
    for kw in CORP_KEYWORDS:
        if kw in upper:
            return "WC100"
    return "WI120"

# ── Field coordinates (reportlab: y = 0 at bottom) ───────────────────
# All x/y derived from pdfplumber rect/edge analysis of template.pdf

# Dates – 8 digit boxes per date (MMDDYYYY, slashes pre-printed on form)
# From: boxes x=151.5–256.8  |  To: boxes x=399.1–504.4
FROM_DATE_X = 151.5
TO_DATE_X   = 399.1
DATE_Y      = 820        # reportlab baseline (box spans rl y=813.7–829.6)
DATE_BOX_W  = 13.16      # exact: 105.3pt / 8 boxes

# TIN – 4 segments, each box measured from actual PDF rectangles
# Seg1: x=207.2–246.8  Seg2: x=258.9–298.4  Seg3: x=310.2–349.8  Seg4: x=361.5–435.4
TIN_SEGS = [
    (207.2, 13.2),    # seg 1: 3 digits  (39.6pt / 3)
    (258.9, 13.2),    # seg 2: 3 digits
    (310.2, 13.2),    # seg 3: 3 digits
    (361.5, 14.78),   # seg 4: 5 digits  (73.9pt / 5)
]
PAYEE_TIN_SEGS = TIN_SEGS
PAYEE_TIN_Y    = 787     # reportlab baseline (box spans rl y=783.1–798.7)

PAYEE_NAME_X = 38
PAYEE_NAME_Y = 758

PAYEE_ADDR_X = 38
PAYEE_ADDR_Y = 728

PAYEE_ZIP_X  = 541.8
PAYEE_ZIP_Y  = 728
ZIP_BOX_W    = 12.5    # 50pt / 4 digits

# Payor TIN – same x segments, different y
PAYOR_TIN_SEGS = TIN_SEGS
PAYOR_TIN_Y    = 670     # reportlab baseline (box spans rl y=667.5–683.5)

PAYOR_NAME_X = 38
PAYOR_NAME_Y = 642

PAYOR_ADDR_X = 38
PAYOR_ADDR_Y = 614

PAYOR_ZIP_X  = 541.8
PAYOR_ZIP_Y  = 614

# Part III – column right edges measured from PDF vertical lines
# Columns: x end at 220 / 292 / 366 / 438 / 510 / 596
# First data row: pdfplumber y=365.3–378.5  →  reportlab baseline ≈ 560
P3_Y     = 560
P3_ATC_X = 181    # left-align in ATC column  (col x=181–220)
P3_M1_X  = 290    # right-align 1st month     (col right edge x=292)
P3_M2_X  = 364    # right-align 2nd month     (col right edge x=366)
P3_M3_X  = 436    # right-align 3rd month     (col right edge x=438)
P3_TOT_X = 508    # right-align total         (col right edge x=510)
P3_TAX_X = 594    # right-align tax withheld  (col right edge x=596)

# ── Drawing helpers ───────────────────────────────────────────────────

def draw_date(c, mmddyyyy: str, start_x: float, y: float):
    """Write 8 date digits into individual boxes."""
    digits = mmddyyyy  # already MMDDYYYY, no slashes
    half = (DATE_BOX_W - 4) / 2   # centre in box (4 ≈ char width at 7 pt)
    for i, ch in enumerate(digits):
        c.drawString(start_x + i * DATE_BOX_W + half, y, ch)


def draw_tin(c, tin: str, segs, y: float):
    """Write TIN digits into the four box-segments."""
    parts = (tin.strip().split("-") + ["", "", "", ""])[:4]
    for part, (seg_x, bw) in zip(parts, segs):
        half = (bw - 4) / 2
        for j, ch in enumerate(part.strip()):
            c.drawString(seg_x + j * bw + half, y, ch)


def draw_zip(c, zip_code: str, start_x: float, y: float):
    """Write ZIP digits into individual boxes."""
    half = (ZIP_BOX_W - 4) / 2
    for i, ch in enumerate(zip_code.strip()):
        c.drawString(start_x + i * ZIP_BOX_W + half, y, ch)


def draw_right(c, text: str, right_x: float, y: float):
    """Right-align text at right_x."""
    w = c.stringWidth(text, FONT, FONT_SIZE)
    c.drawString(right_x - w, y, text)


def fmt(amount: float) -> str:
    return f"{amount:,.2f}"


# ── Quarter logic ─────────────────────────────────────────────────────

MONTHS = [
    "January", "February", "March",
    "April",   "May",      "June",
    "July",    "August",   "September",
    "October", "November", "December",
]

QUARTER_END_DAY = {3: 31, 6: 30, 9: 30, 12: 31}


def quarter_info(month_num: int, year: int):
    """Return (from_mmddyyyy, to_mmddyyyy, month_in_quarter, quarter_num)."""
    q           = (month_num - 1) // 3 + 1
    m_in_q      = (month_num - 1) % 3 + 1
    q_start_m   = (q - 1) * 3 + 1
    q_end_m     = q * 3
    q_end_d     = QUARTER_END_DAY[q_end_m]
    from_str    = f"{q_start_m:02d}01{year}"
    to_str      = f"{q_end_m:02d}{q_end_d:02d}{year}"
    return from_str, to_str, m_in_q, q


# ── PDF generation ────────────────────────────────────────────────────

def generate_pdf(payee: dict, month_num: int, amount: float, year: int, atc_code: str = "WI120") -> bytes:
    from_str, to_str, m_in_q, q = quarter_info(month_num, year)
    tax   = round(amount * TAX_RATE, 2)
    total = amount

    # Build overlay canvas
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
    c.setFont(FONT, FONT_SIZE)

    # Period
    draw_date(c, from_str, FROM_DATE_X, DATE_Y)
    draw_date(c, to_str,   TO_DATE_X,   DATE_Y)

    # Payee
    draw_tin(c, payee["tin"], PAYEE_TIN_SEGS, PAYEE_TIN_Y)
    c.drawString(PAYEE_NAME_X, PAYEE_NAME_Y, payee["name"])
    c.drawString(PAYEE_ADDR_X, PAYEE_ADDR_Y, payee["address"])
    draw_zip(c, payee["zip"], PAYEE_ZIP_X, PAYEE_ZIP_Y)

    # Payor
    draw_tin(c, PAYOR["tin"], PAYOR_TIN_SEGS, PAYOR_TIN_Y)
    c.drawString(PAYOR_NAME_X, PAYOR_NAME_Y, PAYOR["name"])
    c.drawString(PAYOR_ADDR_X, PAYOR_ADDR_Y, PAYOR["address"])
    draw_zip(c, PAYOR["zip"], PAYOR_ZIP_X, PAYOR_ZIP_Y)

    # Part III
    c.drawString(P3_ATC_X, P3_Y, atc_code)
    if m_in_q == 1:
        draw_right(c, fmt(amount), P3_M1_X, P3_Y)
    elif m_in_q == 2:
        draw_right(c, fmt(amount), P3_M2_X, P3_Y)
    else:
        draw_right(c, fmt(amount), P3_M3_X, P3_Y)
    draw_right(c, fmt(total), P3_TOT_X, P3_Y)
    draw_right(c, fmt(tax),   P3_TAX_X, P3_Y)

    c.save()
    packet.seek(0)

    # Merge with template
    template = PdfReader("template.pdf")
    overlay  = PdfReader(packet)
    writer   = PdfWriter()

    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)
    for i in range(1, len(template.pages)):
        writer.add_page(template.pages[i])

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


# ── Load suppliers ────────────────────────────────────────────────────

def load_suppliers():
    with open("suppliers.json", encoding="utf-8") as f:
        return json.load(f)


# ── Supplier search helper ────────────────────────────────────────────

def search_suppliers(query: str, suppliers: dict) -> list:
    words = query.lower().split()
    results = []
    for key, sup in suppliers.items():
        haystack = f"{key} {sup['name']} {sup.get('display_name', '')}".lower()
        if all(w in haystack for w in words):
            results.append(key)
    return sorted(results)


# ── UI ────────────────────────────────────────────────────────────────

st.title("BIR Form 2307 Generator")
st.markdown('<p style="color:#231f20; font-size:17px; line-height:1.55;">Search your name, select the month of payment, enter your ZIP code and total amount received, then download your filled BIR 2307.</p>', unsafe_allow_html=True)

suppliers = load_suppliers()

if "selected_supplier" not in st.session_state:
    st.session_state.selected_supplier = None

st.divider()

search = st.text_input("Supplier name", placeholder="Start typing supplier name")

chosen_name = None

if search and len(search) >= 4:
    matches = search_suppliers(search, suppliers)
    if len(matches) == 1:
        chosen_name = matches[0]
        st.session_state.selected_supplier = chosen_name
    elif matches:
        pick = st.radio("Select your name:", matches, index=None)
        if pick:
            chosen_name = pick
            st.session_state.selected_supplier = pick
    else:
        st.warning("No match found. Try a different name.")
elif search and len(search) < 4:
    st.caption("Keep typing… (minimum 4 characters)")

if chosen_name is None and st.session_state.selected_supplier and search:
    chosen_name = st.session_state.selected_supplier

if chosen_name and chosen_name in suppliers:
    p = suppliers[chosen_name]
    atc_code = get_atc(p["name"])
    with st.expander("Your details (auto-filled from database)", expanded=True):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.write(f"**Registered Name:** {p['name']}")
            st.write(f"**Address:** {p['address']}")
        with col_b:
            st.write(f"**TIN:** {p['tin']}")
            st.write(f"**ATC:** {atc_code}")

st.divider()

c1, c2 = st.columns(2)
with c1:
    chosen_month = st.selectbox("Month of payment", options=[""] + MONTHS,
                                format_func=lambda x: "— select —" if x == "" else x)
with c2:
    zip_default = ""
    if chosen_name and chosen_name in suppliers:
        zip_default = suppliers[chosen_name].get("zip", "")
    zip_input = st.text_input("ZIP Code", value=zip_default,
                              placeholder="Leave blank if unknown")

if chosen_month:
    m_num = MONTHS.index(chosen_month) + 1
    year  = 2026
    fs, ts, m_in_q, q = quarter_info(m_num, year)
    fd = f"{fs[:2]}/{fs[2:4]}/{fs[4:]}"
    td = f"{ts[:2]}/{ts[2:4]}/{ts[4:]}"
    ordinal = {1: "1st", 2: "2nd", 3: "3rd"}[m_in_q]
    st.info(
        f"**Quarter {q}**  ·  Period: **{fd}** – **{td}**  ·  "
        f"{chosen_month} is the **{ordinal} month** of this quarter"
    )

st.divider()

amount_str = st.text_input("Gross amount (₱)", value="", placeholder="Example: 150000")

amount = 0.0
if amount_str:
    try:
        amount = float(amount_str.replace(",", ""))
    except ValueError:
        st.error("Please enter a valid number.")

components.html("""
<script>
(function() {
    var doc = window.parent.document;
    function formatAmountInputs() {
        var labels = doc.querySelectorAll('[data-testid="stTextInput"] label');
        for (var i = 0; i < labels.length; i++) {
            if (labels[i].textContent.indexOf('Gross amount') !== -1) {
                var container = labels[i].closest('[data-testid="stTextInput"]');
                var input = container ? container.querySelector('input') : null;
                if (input && !input.dataset.formatted) {
                    input.dataset.formatted = 'true';
                    input.addEventListener('input', function(e) {
                        var pos = e.target.selectionStart;
                        var oldLen = e.target.value.length;
                        var raw = e.target.value.replace(/[^0-9.]/g, '');
                        var parts = raw.split('.');
                        parts[0] = parts[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
                        var formatted = parts.length > 1 ? parts[0] + '.' + parts[1] : parts[0];
                        e.target.value = formatted;
                        var newLen = formatted.length;
                        var newPos = pos + (newLen - oldLen);
                        e.target.setSelectionRange(newPos, newPos);
                    });
                }
            }
        }
    }
    setTimeout(formatAmountInputs, 500);
    var obs = new MutationObserver(function() { setTimeout(formatAmountInputs, 100); });
    obs.observe(doc.body, {childList: true, subtree: true});
})();
</script>
""", height=0)

if amount > 0 and chosen_month and chosen_name:
    m_num = MONTHS.index(chosen_month) + 1
    atc_code = get_atc(suppliers[chosen_name]["name"])
    tax = round(amount * TAX_RATE, 2)
    ca, cb = st.columns(2)
    with ca:
        st.metric("Income Payment", f"₱{amount:,.2f}")
    with cb:
        st.metric(f"2% Tax Withheld ({atc_code})", f"₱{tax:,.2f}")

st.divider()

ready = chosen_name and chosen_month and amount > 0

if st.button("Generate & Download PDF", type="primary", disabled=not ready):
    with st.spinner("Filling form…"):
        payee = dict(suppliers[chosen_name])
        if zip_input.strip():
            payee["zip"] = zip_input.strip()
            if suppliers[chosen_name].get("zip", "") != zip_input.strip():
                suppliers[chosen_name]["zip"] = zip_input.strip()
                with open("suppliers.json", "w", encoding="utf-8") as f:
                    json.dump(suppliers, f, indent=2, ensure_ascii=False)

        m_num    = MONTHS.index(chosen_month) + 1
        atc_code = get_atc(payee["name"])
        pdf_data = generate_pdf(payee, m_num, amount, year=2026, atc_code=atc_code)

        safe = chosen_name.replace(",", "").replace(" ", "_").upper()
        fname = f"2307_{safe}_{chosen_month.upper()}_2026.pdf"

    st.success("PDF ready! Click below to download.")
    st.download_button(
        label="Download filled PDF",
        data=pdf_data,
        file_name=fname,
        mime="application/pdf",
    )

st.divider()
st.caption("Proprietary application authored and owned by Arwin Edward M. Bagaslao, contributed to Pixelens Creative Advertising Inc. for internal operational use only. Operational use does not constitute ownership transfer. Ownership retained unless assigned in writing. This application is strictly confidential and may only be used by Pixelens Creative Advertising Inc.")
