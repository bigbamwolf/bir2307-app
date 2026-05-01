# BIR Form 2307 Generator

Web app that fills and downloads **BIR Certificate of Creditable Tax Withheld at Source (Form 2307)** for suppliers of **Pixelens Creative Advertising Inc.**

---

## How to use (for suppliers)

1. Open the app link
2. Select **your name** from the dropdown
3. Select the **month** you received payment
4. Enter the **total amount** you received
5. Click **Generate & Download PDF**

The app auto-fills:
- Your registered name, TIN, and address
- The correct quarter period dates
- The income payment in the right month column
- The 2% withholding tax (ATC: WI120)

---

## Deploy to Streamlit Cloud (one-time setup)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Click **Deploy**

That's it — Streamlit Cloud hosts it for free.

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Update supplier list

When you add a new supplier to the Google Sheets template:

1. Edit `suppliers.json` and add an entry:

```json
"TAB NAME": {
  "display_name": "TAB NAME",
  "name": "LAST NAME, FIRST NAME MIDDLE NAME",
  "tin": "XXX-XXX-XXX-XXXXX",
  "address": "Full registered address",
  "zip": "XXXX"
}
```

2. Or re-run the extraction script:
```bash
python3 fetch_suppliers.py
```

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit web app |
| `template.pdf` | Blank BIR Form 2307 (Jan 2018 ENCS) |
| `suppliers.json` | Supplier database (name, TIN, address, ZIP) |
| `fetch_suppliers.py` | Script to re-extract supplier data from Google Sheets |
| `requirements.txt` | Python dependencies |
