import streamlit as st
import streamlit.components.v1 as components
import json

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="BIR Form 2307 Generator",
    page_icon=None,
    layout="centered",
)
from hardening_layer import inject_hardening
inject_hardening("bir2307")

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

# ── Fill engine (shared module; CITADEL SEAL Q1 = one importable module) ──
# The PDF coordinate map, TIN-segment renderer, quarter/column logic, payor
# constant, ATC helper, and month list now live in fill2307.py. This app and
# the CITADEL/SEAL auto-issuance job import the same module. The manual tool
# keeps its own 2% rate for the self-serve flow (passed in below); the module
# itself bakes no rate and no ATC.
from fill2307 import (
    PAYOR,
    CORP_KEYWORDS,
    MONTHS,
    get_atc,
    quarter_info,
    fill_2307,
)

TAX_RATE = 0.02   # 2 % expanded withholding tax (manual tool default, passed to fill_2307)


def generate_pdf(payee: dict, month_num: int, amount: float, year: int, atc_code: str = "WI120") -> bytes:
    """Thin wrapper preserving the app's original call shape. Delegates to the
    shared fill_2307 module, passing the manual tool's 2% rate explicitly."""
    return fill_2307(
        payee={
            "legal_name": payee.get("name", ""),
            "tin": payee.get("tin", ""),
            "address": payee.get("address", ""),
            "zip": payee.get("zip", ""),
        },
        period={"month": month_num, "year": year},
        amount=amount,
        atc=atc_code,
        ewt_rate=TAX_RATE,
    )


# ── Load suppliers ────────────────────────────────────────────────────

def load_suppliers():
    with open("suppliers.json", encoding="utf-8") as f:
        return json.load(f)


# ── Supplier search helper ────────────────────────────────────────────

def search_suppliers(query: str, suppliers: dict) -> list:
    words = query.lower().split()
    scored = []
    for key, sup in suppliers.items():
        haystack = f"{key} {sup['name']} {sup.get('display_name', '')} {sup.get('trade_name', '')}".lower()
        hits = sum(1 for w in words if w in haystack)
        if hits == len(words):
            scored.append((key, hits + 10))
        elif len(words) >= 2 and hits >= 2:
            scored.append((key, hits))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [s[0] for s in scored]


# ── UI ────────────────────────────────────────────────────────────────

st.image("pixelens-logo.png", width=220)
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

amount_label = "Income payment (₱)"
if chosen_name and chosen_name in suppliers:
    sup_name = suppliers[chosen_name]["name"].upper()
    is_corp = any(kw in sup_name for kw in CORP_KEYWORDS)
    if is_corp:
        amount_label = "Vatable Sales (₱)"
    else:
        amount_label = "Total Sales (₱)"

amount_str = st.text_input(amount_label, value="", placeholder="Example: 150,000")
st.caption("Enter Vatable Sales if VAT registered, or Total Sales if non-VAT. This is the amount before withholding tax.")

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
            if (labels[i].textContent.indexOf('Sales') !== -1 || labels[i].textContent.indexOf('Income payment') !== -1) {
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
