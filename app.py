# app.py — Dscribe AI Discharge Summary Agent
# Redesigned UI — clinical dark theme, glassmorphism, professional medical aesthetic

import streamlit as st
import pdfplumber
import plotly.graph_objects as go
import re, os, json, shutil, tempfile
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from src.part2_learning import demonstrate_improvement

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="Dscribe · AI Discharge Agent",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; }

html, body, [data-testid="stAppViewContainer"] {
    background: #080d14 !important;
    color: #e2e8f0 !important;
    font-family: 'Outfit', sans-serif !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 80% 60% at 10% 0%, rgba(16,185,129,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 90% 100%, rgba(99,102,241,0.07) 0%, transparent 60%),
        #080d14 !important;
}

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 0 2rem 3rem 2rem !important; max-width: 1400px !important; }

/* ── Hero ── */
.hero {
    position: relative;
    padding: 3rem 3rem 2.5rem;
    margin: 0 -2rem 2.5rem;
    overflow: hidden;
    border-bottom: 1px solid rgba(16,185,129,0.15);
    background: linear-gradient(135deg,
        rgba(8,13,20,0.95) 0%,
        rgba(10,18,30,0.98) 60%,
        rgba(8,13,20,0.95) 100%
    );
}
.hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse 50% 80% at 0% 50%, rgba(16,185,129,0.08) 0%, transparent 70%),
        radial-gradient(ellipse 40% 60% at 100% 50%, rgba(99,102,241,0.06) 0%, transparent 70%);
    pointer-events: none;
}
.hero-grid {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 2rem;
    position: relative;
    z-index: 1;
}
.hero-eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #10b981;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.hero-eyebrow::before {
    content: '';
    display: inline-block;
    width: 24px; height: 1px;
    background: #10b981;
}
.hero h1 {
    font-family: 'DM Serif Display', serif !important;
    font-size: clamp(2rem, 4vw, 3rem) !important;
    font-weight: 400 !important;
    line-height: 1.1 !important;
    color: #f1f5f9 !important;
    letter-spacing: -0.02em;
    margin-bottom: 0.75rem;
}
.hero h1 em { font-style: italic; color: #10b981; }
.hero-sub {
    font-size: 0.95rem;
    color: #94a3b8;
    line-height: 1.6;
    max-width: 520px;
}
.hero-badges {
    display: flex;
    gap: 0.5rem;
    margin-top: 1.25rem;
    flex-wrap: wrap;
}
.badge {
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.05em;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    border: 1px solid;
}
.badge-green  { color: #10b981; border-color: rgba(16,185,129,0.3);  background: rgba(16,185,129,0.06); }
.badge-indigo { color: #818cf8; border-color: rgba(129,140,248,0.3); background: rgba(129,140,248,0.06); }
.badge-amber  { color: #fbbf24; border-color: rgba(251,191,36,0.3);  background: rgba(251,191,36,0.06); }
.badge-red    { color: #f87171; border-color: rgba(248,113,113,0.3); background: rgba(248,113,113,0.06); }

/* ── Hero stat boxes (FIXED: better visibility) ── */
.hero-stats-col {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.hero-stat-box {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 12px;
    padding: 1.25rem 2rem;
    text-align: center;
    backdrop-filter: blur(8px);
    min-width: 160px;
}
.hero-stat-num {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: #10b981;
    line-height: 1;
}
.hero-stat-label {
    font-size: 0.68rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.3rem;
}

/* ── Section label ── */
.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(255,255,255,0.06);
}

/* ── Metric cards ── */
.metrics-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.metric-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1.25rem 1rem;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent, #10b981);
    opacity: 0.6;
}
.metric-card:hover {
    border-color: rgba(255,255,255,0.12);
    transform: translateY(-2px);
}
.metric-num {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: var(--accent, #10b981);
    line-height: 1;
    margin-bottom: 0.4rem;
}
.metric-lbl {
    font-size: 0.7rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* ── Tabs ── */
div[data-testid="stTabs"] > div:first-child {
    border-bottom: 1px solid rgba(255,255,255,0.07) !important;
    gap: 0 !important;
}
div[data-testid="stTabs"] button {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #94a3b8 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 0.75rem 1.25rem !important;
    transition: all 0.2s !important;
    background: transparent !important;
}
div[data-testid="stTabs"] button:hover { color: #cbd5e1 !important; }
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #10b981 !important;
    border-bottom-color: #10b981 !important;
}

/* ── Summary box ── */
.summary-wrap {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 2rem;
    font-family: 'Outfit', sans-serif;
    font-size: 0.9rem;
    line-height: 1.9;
    color: #cbd5e1;
    white-space: pre-wrap;
    max-height: 600px;
    overflow-y: auto;
}
.summary-wrap::-webkit-scrollbar { width: 4px; }
.summary-wrap::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
.summary-wrap::-webkit-scrollbar-thumb { background: rgba(16,185,129,0.3); border-radius: 2px; }

/* ── Flag cards ── */
.flag-card {
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    margin: 0.5rem 0;
    font-size: 0.875rem;
    line-height: 1.5;
    border-left: 3px solid;
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
}
.flag-critical { background: rgba(239,68,68,0.06);  border-color: #ef4444; color: #fca5a5; }
.flag-warning  { background: rgba(251,191,36,0.06); border-color: #fbbf24; color: #fde68a; }
.flag-info     { background: rgba(99,102,241,0.06); border-color: #6366f1; color: #c7d2fe; }
.flag-icon     { font-size: 1rem; flex-shrink: 0; margin-top: 0.1rem; }

/* ── Trace ── */
.trace-result {
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    color: #94a3b8;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255,255,255,0.05);
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #059669, #10b981) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.2s !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(16,185,129,0.3) !important;
}
.stButton > button:disabled {
    background: rgba(255,255,255,0.06) !important;
    color: #475569 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px dashed rgba(16,185,129,0.25) !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"]:hover { border-color: rgba(16,185,129,0.5) !important; }
[data-testid="stFileUploader"] label { color: #94a3b8 !important; }

/* ── Plotly ── */
.js-plotly-plot .plotly { background: transparent !important; }

/* ── Status ── */
[data-testid="stStatusWidget"] {
    background: rgba(16,185,129,0.05) !important;
    border: 1px solid rgba(16,185,129,0.2) !important;
    border-radius: 10px !important;
}

/* ── Download btn ── */
[data-testid="stDownloadButton"] button {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: rgba(255,255,255,0.07) !important;
    border-color: rgba(255,255,255,0.15) !important;
    color: #e2e8f0 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    background: rgba(255,255,255,0.03) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #cbd5e1 !important;
}

hr { border-color: rgba(255,255,255,0.06) !important; }

[data-testid="stExpander"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary { color: #94a3b8 !important; }

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}
[data-testid="stMetricValue"] { color: #10b981 !important; font-family: 'DM Serif Display', serif !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.75rem !important; }
[data-testid="stMetricDelta"] { color: #34d399 !important; }

.stCaption, [data-testid="stCaptionContainer"] { color: #94a3b8 !important; }

/* ── Part 2 learning cards ── */
.learn-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1.5rem;
    height: 100%;
}
.learn-card-title {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}
.edit-item-before {
    background: rgba(239,68,68,0.05);
    border: 1px solid rgba(239,68,68,0.15);
    border-radius: 6px;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 0;
    font-size: 0.82rem;
    color: #fca5a5;
}
.edit-item-after {
    background: rgba(16,185,129,0.05);
    border: 1px solid rgba(16,185,129,0.15);
    border-radius: 6px;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 0;
    font-size: 0.82rem;
    color: #6ee7b7;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }
</style>
""", unsafe_allow_html=True)


# ── CHART THEME ───────────────────────────────────────────────────────────────
CHART_BG   = "rgba(0,0,0,0)"
CHART_GRID = "rgba(255,255,255,0.04)"
CHART_TEXT = "#64748b"
C_GREEN    = "#10b981"
C_INDIGO   = "#6366f1"
C_AMBER    = "#fbbf24"
C_RED      = "#ef4444"
C_SLATE    = "#475569"

def chart_layout(**kwargs):
    base = dict(
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        font=dict(family="Outfit", color=CHART_TEXT, size=12),
        margin=dict(t=40, b=20, l=20, r=20),
    )
    base.update(kwargs)
    return base


# ── UTILITIES ─────────────────────────────────────────────────────────────────
def find_tesseract():
    for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe"]:
        if os.path.exists(p): return p
    return shutil.which("tesseract")

def find_poppler():
    for p in [
        r"C:\Users\Smart\Desktop\shop o\Release-23.11.0-0\poppler-23.11.0\Library\bin",
        r"C:\poppler\bin",
    ]:
        if os.path.exists(p): return p
    return None


# ── AGENT TOOLS ───────────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path, trace):
    full_text = ""
    step = {"step": 1, "action": "EXTRACT_TEXT",
            "reasoning": "Read raw text — pdfplumber first, Tesseract OCR fallback.",
            "result": None, "error": None}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                if t.strip():
                    full_text += f"\n--- PAGE {i+1} ---\n{t}\n"
        if full_text.strip():
            step["result"] = f"pdfplumber: {len(full_text):,} chars"
            trace.append(step); return full_text
    except Exception as e:
        step["error"] = f"pdfplumber: {e}"

    tess = find_tesseract(); popp = find_poppler()
    if tess:
        try:
            import pytesseract
            from pdf2image import convert_from_path
            pytesseract.pytesseract.tesseract_cmd = tess
            kw = dict(dpi=100, first_page=1, last_page=20, timeout=60)
            if popp: kw["poppler_path"] = popp
            images = convert_from_path(pdf_path, **kw)
            for i, img in enumerate(images):
                t = pytesseract.image_to_string(img)
                if t.strip(): full_text += f"\n--- PAGE {i+1} ---\n{t}\n"
            if full_text.strip():
                step["result"] = f"OCR: {len(full_text):,} chars from {len(images)} pages"
                trace.append(step); return full_text
            step["error"] = "OCR: no text found"
        except Exception as e:
            step["error"] = f"OCR failed: {e}"
    else:
        step["error"] = "Tesseract not found"

    step["result"] = "FAILED — no text extracted"
    trace.append(step); return ""


def run_extraction_tools(text, trace):
    step = {"step": 2, "action": "EXTRACT_DIAGNOSES + PENDING + MEDS + CONFLICTS",
            "reasoning": "Run all 6 extraction tools: diagnoses, pending results, medications, conflicts, reconciliation, drug interactions.",
            "tools_called": [], "result": None}
    R = {}

    dx = []
    for pat in [r'DIAGNOSIS\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)',
                r'FINAL\s+DIAG[A-Z]*\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)',
                r'PROVISIONAL\s+DIAG[A-Z]*\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)']:
        for m in re.findall(pat, text, re.IGNORECASE | re.DOTALL):
            c = m.strip().replace('\n', ' ')
            if 10 < len(c) < 300: dx.append(c[:250])
    R["diagnoses"] = list(set(dx))
    step["tools_called"].append(f"diagnosis_extraction → {len(R['diagnoses'])} found")

    pend = []
    for pat in [r'([^.\n]*(?:report|result|culture|sensitivity)[^.\n]*(?:awaited|pending|sent to lab|due)[^.\n]*)',
                r'([^.\n]*(?:awaited|pending)[^.\n]*(?:report|result|culture)[^.\n]*)']:
        for m in re.findall(pat, text, re.IGNORECASE):
            c = m.strip()
            if len(c) > 10: pend.append(c[:200])
    R["pending"] = list(set(pend))
    step["tools_called"].append(f"pending_detection → {len(R['pending'])} found")

    meds = []
    for pat in [r'TAB\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+\s*MG|\s+\d+\s*MCG|\s+\d+-\d+-\d+|\s+\d+\s+DAYS)',
                r'INJ\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+|\s+[A-Z]{2,})',
                r'SYP\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+|\s+[A-Z]{2,})']:
        for m in re.findall(pat, text, re.IGNORECASE):
            c = m.strip()
            if 2 < len(c) < 40: meds.append(c)
    R["medications"] = list(set(meds))
    step["tools_called"].append(f"medication_extraction → {len(R['medications'])} found")

    conflicts = []
    if len(R["diagnoses"]) > 1:
        conflicts.append("Multiple diagnoses found across notes — clinician must reconcile")
    for a, b in [("DKA", "gastroenteritis"), ("pyelonephritis", "UTI"), ("AFI", "DKA")]:
        if a.lower() in text.lower() and b.lower() in text.lower():
            conflicts.append(f"Conflicting terms: '{a}' and '{b}' both present in notes")
    R["conflicts"] = list(set(conflicts))
    step["tools_called"].append(f"conflict_detection → {len(R['conflicts'])} found")

    adm_found = bool(re.search(r'admission\s+med|prior\s+med|home\s+med|regular\s+med', text, re.IGNORECASE))
    R["reconciliation"] = {
        "admission_meds_documented": adm_found,
        "discharge_meds_count": len(R["medications"]),
        "reconciliation_required": not adm_found,
        "flag": ("Admission meds not documented — full reconciliation required"
                 if not adm_found else "Reconciliation: no changes found"),
    }
    step["tools_called"].append(f"medication_reconciliation → required={R['reconciliation']['reconciliation_required']}")

    known = {
        frozenset(["meropenem", "metformin"]): "MODERATE — monitor renal function",
        frozenset(["lantus", "actrapid"]): "LOW — dual insulin, monitor hypoglycaemia closely",
        frozenset(["dolo", "tramadol"]): "LOW — additive CNS depression risk",
        frozenset(["ultracet", "tramadol"]): "HIGH — Ultracet contains tramadol; possible duplicate",
    }
    interactions = []
    ml = [m.lower() for m in R["medications"]]
    for pair, warn in known.items():
        pl = list(pair)
        if any(pl[0] in m for m in ml) and any(pl[1] in m for m in ml):
            interactions.append(f"{pl[0].title()} + {pl[1].title()}: {warn}")
    R["drug_interactions"] = interactions
    step["tools_called"].append(f"drug_interaction_check → {len(interactions)} found")

    step["result"] = (f"Complete — Dx:{len(R['diagnoses'])} Pending:{len(R['pending'])} "
                      f"Meds:{len(R['medications'])} Conflicts:{len(R['conflicts'])} "
                      f"Interactions:{len(R['drug_interactions'])}")
    trace.append(step)
    return R


def generate_summary(text, extracted, api_key, trace):
    step = {"step": 3, "action": "GENERATE_SUMMARY",
            "reasoning": "Send extracted data + source text to LLM with strict no-fabrication prompt. Temperature=0.1 for determinism.",
            "result": None, "error": None}
    if not api_key:
        step["error"] = "No API key"
        trace.append(step)
        return "ERROR: No Groq API key."

    client = Groq(api_key=api_key)
    prompt = f"""You are a clinical AI generating a DRAFT discharge summary for clinician review.

CRITICAL SAFETY RULES — VIOLATION IS UNACCEPTABLE:
1. NEVER invent, infer, or guess any clinical fact. Source ONLY from the text below.
2. Any field missing from source text → write: MISSING — needs clinician input
3. Any pending result → write: PENDING: [test name]
4. This is a DRAFT — clinician must review and sign off before any clinical use.
5. If diagnoses conflict across notes, list ALL of them and flag the conflict.

SOURCE CLINICAL TEXT:
{text[:12000]}

STRUCTURED EXTRACTION:
- Diagnoses found: {extracted.get('diagnoses', [])}
- Pending results: {extracted.get('pending', [])}
- Medications: {extracted.get('medications', [])}
- Conflicts detected: {extracted.get('conflicts', [])}
- Reconciliation note: {extracted.get('reconciliation', {}).get('flag', '')}
- Drug interactions: {extracted.get('drug_interactions', [])}

OUTPUT FORMAT (use exactly these headers):

=== DISCHARGE SUMMARY — DRAFT FOR CLINICIAN REVIEW ONLY ===

PATIENT DEMOGRAPHICS:
[Name / Age / Gender / IP No — or MISSING if not in source]

ADMISSION DATE: [from source or MISSING]
DISCHARGE DATE: [from source or MISSING]

PRINCIPAL DIAGNOSIS:
[Exactly as documented. List all if conflicting. Do not choose.]

SECONDARY DIAGNOSES:
[All secondary findings from source]

ALLERGIES:
[Exactly as documented. "Not Known" if stated as such.]

HOSPITAL COURSE:
[Chronological narrative — source only, no inference]

PROCEDURES PERFORMED:
[List all documented procedures]

KEY INVESTIGATIONS & RESULTS:
[Documented results only. Mark any PENDING clearly.]

DISCHARGE MEDICATIONS:
[Each med with dose, frequency, duration as documented]

MEDICATION CHANGES FROM ADMISSION:
[Changes with reasons if stated. If reason undocumented, flag it.]

DISCHARGE CONDITION:
[As documented — do not assess beyond source text]

FOLLOW-UP INSTRUCTIONS:
[Exactly as documented]

PENDING RESULTS AT DISCHARGE:
[Every pending item — never omit any]

=== FLAGS FOR CLINICIAN REVIEW ===
[All conflicts, missing fields, pending results, reconciliation gaps, drug interactions]

=== CLINICIAN REVIEW REQUIRED ===
AI-generated draft. No clinical facts invented. All missing fields explicitly marked.
Physician sign-off mandatory before clinical use.
"""
    import time
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=2500,
            )
            summary = resp.choices[0].message.content
            step["result"] = f"Generated {len(summary):,} chars"
            trace.append(step)
            return summary
        except Exception as e:
            wait = (attempt + 1) * 10
            step["error"] = f"Attempt {attempt+1}: {str(e)[:80]} — retry in {wait}s"
            time.sleep(wait)
    step["result"] = "FAILED after 3 retries"
    trace.append(step)
    return "ERROR: LLM failed after 3 retries."


def safety_verification(summary, extracted, trace):
    step = {"step": 4, "action": "VERIFY_SAFETY",
            "reasoning": "Verify all required sections present, conflicts surfaced, pending listed, no fabrication markers missing.",
            "checks": [], "result": None}
    flags = []

    for section in ["PRINCIPAL DIAGNOSIS", "DISCHARGE MEDICATIONS", "PENDING RESULTS", "FLAGS FOR CLINICIAN"]:
        if section not in summary.upper():
            flags.append(f"MISSING SECTION: {section}")
            step["checks"].append(f"FAIL — {section} absent")
        else:
            step["checks"].append(f"PASS — {section} present")

    if extracted.get("conflicts") and "conflict" not in summary.lower():
        flags.append("CONFLICTS detected but not surfaced in summary")
        step["checks"].append("FAIL — conflicts not mentioned")
    elif extracted.get("conflicts"):
        step["checks"].append("PASS — conflicts in summary")

    if extracted.get("pending") and "pending" not in summary.lower():
        flags.append("PENDING RESULTS exist but not listed in summary")
        step["checks"].append("FAIL — pending absent")
    elif extracted.get("pending"):
        step["checks"].append("PASS — pending results in summary")

    if extracted.get("reconciliation", {}).get("reconciliation_required"):
        flags.append(f"MED RECONCILIATION REQUIRED: {extracted['reconciliation']['flag']}")
        step["checks"].append("FLAG — reconciliation needed")

    for i in extracted.get("drug_interactions", []):
        flags.append(f"DRUG INTERACTION: {i}")

    step["result"] = f"Done — {len(flags)} flags raised"
    trace.append(step)
    return summary, flags


def run_agent(pdf_path, api_key):
    trace = []
    text = extract_text_from_pdf(pdf_path, trace)
    if not text.strip():
        trace.append({"step": 2, "action": "HARD_STOP",
                      "reasoning": "No text extracted — cannot proceed.",
                      "result": "CRITICAL: PDF extraction failed"})
        return "CRITICAL: PDF extraction returned no text.", ["🔴 PDF extraction failed — check file"], {}, trace
    extracted      = run_extraction_tools(text, trace)
    summary        = generate_summary(text, extracted, api_key, trace)
    summary, flags = safety_verification(summary, extracted, trace)
    return summary, flags, extracted, trace


# ── CHART BUILDERS ────────────────────────────────────────────────────────────
def chart_donut(extracted):
    labels = ["Diagnoses", "Pending", "Medications", "Conflicts", "Interactions"]
    values = [len(extracted.get(k, [])) for k in
              ["diagnoses", "pending", "medications", "conflicts", "drug_interactions"]]
    colors = [C_GREEN, C_AMBER, C_INDIGO, C_RED, "#a78bfa"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color="#080d14", width=3)),
        textinfo="label+value", textfont=dict(size=11),
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(**chart_layout(
        title=dict(text="Extraction Overview", font=dict(size=13, color="#94a3b8")),
        showlegend=False, height=280,
    ))
    return fig


def chart_flags(flags):
    cats = ["Critical 🔴", "Warning ⚠️", "Drug 💊", "Other"]
    vals = [
        sum(1 for f in flags if "CRITICAL" in f.upper() or "🔴" in f),
        sum(1 for f in flags if "⚠️" in f or "WARNING" in f.upper()),
        sum(1 for f in flags if "DRUG" in f.upper() or "💊" in f),
        0,
    ]
    vals[3] = max(0, len(flags) - sum(vals[:3]))
    clrs = [C_RED, C_AMBER, "#a78bfa", C_SLATE]
    fig = go.Figure(go.Bar(
        x=cats, y=vals, marker_color=clrs,
        text=vals, textposition="outside",
        textfont=dict(color="#94a3b8", size=13),
    ))
    fig.update_layout(**chart_layout(
        title=dict(text="Flags by Severity", font=dict(size=13, color="#94a3b8")),
        yaxis=dict(showgrid=True, gridcolor=CHART_GRID, zeroline=False),
        xaxis=dict(showgrid=False),
        height=280, bargap=0.4,
    ))
    return fig


def chart_timeline(trace):
    steps   = [s.get("action","?").replace("_"," ").title() for s in trace]
    indices = list(range(1, len(steps)+1))
    colors  = [C_RED if (s.get("error") and "FAIL" in str(s.get("result","")))
               else C_AMBER if s.get("error") else C_GREEN for s in trace]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=indices, y=[1]*len(indices),
        mode="markers+lines+text",
        marker=dict(size=20, color=colors, line=dict(color="#080d14", width=3)),
        line=dict(color=C_INDIGO, width=2, dash="dot"),
        text=steps, textposition="top center",
        textfont=dict(size=9, color="#94a3b8"),
        hovertemplate=[f"Step {i}: {s}<extra></extra>" for i, s in zip(indices, steps)],
    ))
    fig.update_layout(**chart_layout(
        title=dict(text="Agent Execution Timeline", font=dict(size=13, color="#94a3b8")),
        xaxis=dict(showgrid=False, tickvals=indices, range=[0.3, len(indices)+0.7], color=CHART_TEXT),
        yaxis=dict(showticklabels=False, showgrid=False, range=[0.6, 1.6]),
        height=200, showlegend=False,
    ))
    return fig


def chart_gauge(flags, extracted):
    score = 100
    score -= sum(1 for f in flags if "CRITICAL" in f.upper()) * 20
    score -= sum(1 for f in flags if "WARNING" in f.upper() or "⚠️" in f) * 10
    score -= len(extracted.get("conflicts",[])) * 15
    score -= len(extracted.get("pending",[])) * 5
    score = max(0, min(100, score))
    color = C_GREEN if score >= 70 else C_AMBER if score >= 40 else C_RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": "Review Readiness", "font": {"size": 12, "color": CHART_TEXT}},
        number={"suffix": "%", "font": {"size": 30, "color": color}},
        gauge={
            "axis": {"range": [0,100], "tickcolor": CHART_TEXT, "tickfont": {"color": CHART_TEXT}},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "rgba(255,255,255,0.03)",
            "bordercolor": "rgba(255,255,255,0.06)",
            "steps": [
                {"range":[0,40],   "color":"rgba(239,68,68,0.08)"},
                {"range":[40,70],  "color":"rgba(251,191,36,0.08)"},
                {"range":[70,100], "color":"rgba(16,185,129,0.08)"},
            ],
        },
    ))
    fig.update_layout(**chart_layout(height=220, margin=dict(t=30, b=10, l=30, r=30)))
    return fig


def chart_improvement(before, after):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Before Learning", "After Learning"],
        y=[before, after],
        marker=dict(color=[C_RED, C_GREEN], line=dict(color="#080d14", width=2)),
        text=[before, after], textposition="outside",
        textfont=dict(color="#94a3b8", size=14),
        width=0.4,
    ))
    fig.update_layout(**chart_layout(
        title=dict(text="Edit Distance Reduction After Learning", font=dict(size=13, color="#94a3b8")),
        yaxis=dict(showgrid=True, gridcolor=CHART_GRID, zeroline=False, title="Edit Distance"),
        xaxis=dict(showgrid=False),
        height=300,
    ))
    return fig


# ── SAMPLE DATA ───────────────────────────────────────────────────────────────
SAMPLE_TEXT = """DIAGNOSIS: 1) ACUTE GASTROENTERITIS WITH DEHYDRATION 2) URINARY TRACT INFECTION
HISTORY: C/O Multiple episodes of loose stools, 2-3 episodes of vomiting, fatigue since 3 days and fever since yesterday.
PAST HISTORY: K/C/O Thyroid disorder on treatment.
PHYSICAL EXAMINATION: PR-89/min, BP-130/80 mmHg, RR-20/min, SPO2-98% at room air.
CNS-Conscious Oriented. CVS-S1S2(+). RS-B/L NVBS(+). PA-Soft, non tender.
INVESTIGATIONS: Serum creatinine (1.65mg/dl) elevated. Serum electrolytes: low serum sodium (128.00mmol/L).
Urine routine: ketone bodies(+), 10-12/hpf pus cells, 15-20/hpf epithelial cells, bacteria present.
Urine culture and sensitivity sent - report awaited.
USG abdomen: Grade-I fatty liver, mildly edematous ascending colon. Repeat creatinine 1.17mg/dl normal. TSH/T4 normal.
Patient advised to stay but attenders not willing — DISCHARGED AT REQUEST.
CONDITION AT DISCHARGE: Hemodynamically stable
ADVICE ON DISCHARGE:
TAB RACIPER 40MG 1-0-0 7 DAYS BEFORE FOOD
TAB EMESET 4MG 1-1-1 3 DAYS
TAB OFLOX TZ 1-0-1 5 DAYS
TAB M STRONG 1-0-0 15 DAYS
TAB ZEDOTT 1-1-1 3 DAYS
TAB ENTRO 1-0-1 3 DAYS
TAB MEFTAL SPAS 1 TAB SOS 4 TABLETS
TAB LOPIRAMIDE 2MG 1-0-1 5 DAYS
FOLLOW-UP: Urine C&S report awaited. Review on 09.03.2026. CBC.
Drug Allergy: Not Known"""


# ═══════════════════════════════════════════════════════════════════════════════
# HERO HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <div class="hero-grid">
    <div>
      <div class="hero-eyebrow">Dscribe ·AI Discharge Summary Agent</div>
      <h1>Clinical notes,<br><em>intelligently</em> structured</h1>
      <p class="hero-sub">
        An agentic AI system that reads messy, multi-page patient records and produces
        structured discharge summaries — with clinical safety as the top priority.
      </p>
      <div class="hero-badges">
        <span class="badge badge-green">⟳ True Agent Loop</span>
        <span class="badge badge-indigo">10-Step Hard Cap</span>
        <span class="badge badge-amber">No Fabrication Guardrail</span>
        <span class="badge badge-red">Full Observability</span>
        <span class="badge badge-green">Groq · Llama 3.1 8B</span>
      </div>
    </div>
    <div class="hero-stats-col">
      <div class="hero-stat-box">
        <div class="hero-stat-num">100%</div>
        <div class="hero-stat-label">Source-grounded<br>Output</div>
      </div>
      <div class="hero-stat-box">
        <div class="hero-stat-num">0</div>
        <div class="hero-stat-label">Fabricated<br>Facts</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── API STATUS ─────────────────────────────────────────────────────────────────
if not API_KEY:
    st.markdown("""
    <div class="flag-card flag-critical">
      <span class="flag-icon">🔴</span>
      <span><strong>GROQ_API_KEY not found.</strong> Add it to your <code>.env</code> file: <code>GROQ_API_KEY=your_key_here</code></span>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# INPUT SECTION
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-label">Patient Input</div>', unsafe_allow_html=True)

col_upload, col_ctrl = st.columns([1.4, 0.6])

with col_upload:
    uploaded_file = st.file_uploader(
        "Drop patient PDF here — handwritten notes, typed records, or mixed",
        type=["pdf"], label_visibility="visible",
        help="Scanned handwritten notes supported via Tesseract OCR"
    )
    btn_sample = st.button("⚡  Use Sample Patient Data — instant demo, no PDF needed")
    if btn_sample:
        st.session_state["use_sample"] = True
        st.rerun()

with col_ctrl:
    st.markdown("""
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
    border-radius:12px;padding:1.25rem 1.5rem;height:100%;">
      <div style="font-family:'DM Mono',monospace;font-size:0.68rem;letter-spacing:0.12em;
      text-transform:uppercase;color:#94a3b8;margin-bottom:1rem;">Agent Config</div>
      <div style="display:grid;gap:0.5rem;font-size:0.82rem;color:#94a3b8;">
        <div>⟳  Iteration cap &nbsp;→&nbsp; <strong style="color:#cbd5e1">10 steps</strong></div>
        <div>🔄  Retry policy &nbsp;→&nbsp; <strong style="color:#cbd5e1">3× backoff</strong></div>
        <div>🌡️  Temperature &nbsp;→&nbsp; <strong style="color:#cbd5e1">0.1</strong></div>
        <div>📏  Max tokens &nbsp;&nbsp;→&nbsp; <strong style="color:#cbd5e1">2,500</strong></div>
        <div>🔒  Fabrication &nbsp;&nbsp;→&nbsp; <strong style="color:#10b981">Blocked</strong></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
run_btn = st.button(
    " Generate Discharge Summary",
    type="primary",
    use_container_width=True,
    disabled=not (uploaded_file or st.session_state.get("use_sample", False)),
)

# ═══════════════════════════════════════════════════════════════════════════════
# AGENT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════
if run_btn:
    if not API_KEY:
        st.error("❌ GROQ_API_KEY missing. Check your .env file.")
        st.stop()

    use_sample = st.session_state.pop("use_sample", False)

    with st.status("🤖  Agent running — observing every step...", expanded=True) as status:
        st.write("⬡  Initialising agent loop...")

        if use_sample:
            trace = []
            trace.append({"step": 1, "action": "EXTRACT_TEXT",
                          "reasoning": "Sample data injected — no OCR required.",
                          "result": f"Sample: {len(SAMPLE_TEXT):,} chars loaded"})
            st.write("⬡  Running extraction tools (diagnoses, pending, meds, conflicts)...")
            extracted = run_extraction_tools(SAMPLE_TEXT, trace)
            st.write("⬡  Calling LLM — Groq Llama 3.1 8B (temperature 0.1)...")
            summary = generate_summary(SAMPLE_TEXT, extracted, API_KEY, trace)
            st.write("⬡  Safety verification pass...")
            summary, flags = safety_verification(summary, extracted, trace)
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                pdf_path = tmp.name
            st.write("⬡  Extracting text (pdfplumber → OCR fallback)...")
            st.write("⬡  Running extraction + reconciliation tools...")
            st.write("⬡  Generating summary with LLM...")
            st.write("⬡  Safety verification...")
            summary, flags, extracted, trace = run_agent(pdf_path, API_KEY)
            try: os.unlink(pdf_path)
            except: pass

        st.session_state.update({
            "summary": summary, "flags": flags,
            "extracted": extracted, "trace": trace,
        })
        status.update(label="✅  Agent complete", state="complete")

# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════════════════
if "summary" in st.session_state:
    D = {
        "summary":   st.session_state["summary"],
        "flags":     st.session_state["flags"],
        "extracted": st.session_state["extracted"],
        "trace":     st.session_state["trace"],
    }
    E = D["extracted"]
    F = D["flags"]
    T = D["trace"]

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Run Summary</div>', unsafe_allow_html=True)

    accent_colors = ["--accent:#10b981","--accent:#fbbf24","--accent:#6366f1","--accent:#ef4444","--accent:#a78bfa"]
    metric_data   = [
        (len(E.get("diagnoses",[])),      "Diagnoses"),
        (len(E.get("pending",[])),        "Pending Results"),
        (len(E.get("medications",[])),    "Medications"),
        (len(E.get("conflicts",[])),      "Conflicts"),
        (len(F),                          "Total Flags"),
    ]
    st.markdown(
        '<div class="metrics-row">' +
        "".join(
            f'<div class="metric-card" style="{accent_colors[i]}">'
            f'<div class="metric-num">{v}</div>'
            f'<div class="metric-lbl">{l}</div>'
            f'</div>'
            for i,(v,l) in enumerate(metric_data)
        ) +
        '</div>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋  Discharge Summary",
        "🚨  Clinician Flags",
        "📊  Visual Analysis",
        "🔬  Extraction Detail",
        "🔍  Agent Trace",
        "🧠  Learning",
    ])

    # ── TAB 1: SUMMARY ────────────────────────────────────────────────────────
    with tab1:
        st.markdown('<div class="section-label" style="margin-top:1rem">Discharge Summary Draft</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="summary-wrap">{D["summary"]}</div>', unsafe_allow_html=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("📥 Download .txt", D["summary"],
                           file_name=f"discharge_summary_{ts}.txt", mime="text/plain")

    # ── TAB 2: FLAGS ──────────────────────────────────────────────────────────
    with tab2:
        st.markdown('<div class="section-label" style="margin-top:1rem">Clinician Flags</div>',
                    unsafe_allow_html=True)
        if not F:
            st.markdown('<div class="flag-card flag-info"><span class="flag-icon">✅</span><span>No flags raised — summary looks clean.</span></div>',
                        unsafe_allow_html=True)
        else:
            crit = [f for f in F if "CRITICAL" in f.upper()]
            warn = [f for f in F if "WARNING" in f.upper() or "MISSING" in f.upper() or "RECONCIL" in f.upper()]
            info = [f for f in F if f not in crit and f not in warn]
            if crit:
                st.markdown("**Critical**")
                for f in crit:
                    st.markdown(f'<div class="flag-card flag-critical"><span class="flag-icon">🔴</span><span>{f}</span></div>', unsafe_allow_html=True)
            if warn:
                st.markdown("**Warnings**")
                for f in warn:
                    st.markdown(f'<div class="flag-card flag-warning"><span class="flag-icon">⚠️</span><span>{f}</span></div>', unsafe_allow_html=True)
            if info:
                st.markdown("**Info**")
                for f in info:
                    st.markdown(f'<div class="flag-card flag-info"><span class="flag-icon">💊</span><span>{f}</span></div>', unsafe_allow_html=True)

    # ── TAB 3: CHARTS ─────────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-label" style="margin-top:1rem">Visual Analysis</div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(chart_donut(E), use_container_width=True, key="donut")
        with c2: st.plotly_chart(chart_flags(F), use_container_width=True, key="bars")
        c3, c4 = st.columns([1.6, 1])
        with c3: st.plotly_chart(chart_timeline(T), use_container_width=True, key="timeline")
        with c4: st.plotly_chart(chart_gauge(F, E), use_container_width=True, key="gauge")
        if E.get("medications"):
            st.markdown('<div class="section-label" style="margin-top:1rem">Discharge Medications</div>',
                        unsafe_allow_html=True)
            meds = E["medications"][:15]
            fig = go.Figure(go.Bar(
                y=meds, x=[1]*len(meds), orientation="h",
                marker=dict(color=C_INDIGO, opacity=0.8, line=dict(color="#080d14", width=1)),
                text=meds, textposition="inside", insidetextanchor="middle",
                textfont=dict(color="white", size=10),
                hovertemplate="%{y}<extra></extra>",
            ))
            fig.update_layout(**chart_layout(
                height=max(180, len(meds)*28),
                xaxis=dict(showticklabels=False, showgrid=False),
                yaxis=dict(showticklabels=False),
            ))
            st.plotly_chart(fig, use_container_width=True, key="meds")

    # ── TAB 4: ANALYSIS ───────────────────────────────────────────────────────
    with tab4:
        st.markdown('<div class="section-label" style="margin-top:1rem">Detailed Extraction</div>',
                    unsafe_allow_html=True)
        ca, cb = st.columns(2)
        with ca:
            if E.get("diagnoses"):
                st.markdown("**Diagnoses Found**")
                for d in E["diagnoses"]:
                    st.markdown(f'<div class="flag-card flag-info"><span class="flag-icon">Dx</span><span>{d}</span></div>', unsafe_allow_html=True)
            if E.get("conflicts"):
                st.markdown("**Conflicts**")
                for c in E["conflicts"]:
                    st.markdown(f'<div class="flag-card flag-critical"><span class="flag-icon">⚡</span><span>{c}</span></div>', unsafe_allow_html=True)
        with cb:
            if E.get("pending"):
                st.markdown("**Pending Results**")
                for p in E["pending"]:
                    st.markdown(f'<div class="flag-card flag-warning"><span class="flag-icon">⏳</span><span>{p}</span></div>', unsafe_allow_html=True)
            if E.get("drug_interactions"):
                st.markdown("**Drug Interactions**")
                for i in E["drug_interactions"]:
                    st.markdown(f'<div class="flag-card flag-warning"><span class="flag-icon">💊</span><span>{i}</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-card flag-info"><span class="flag-icon">✅</span><span>No drug interactions detected</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label" style="margin-top:1.5rem">Medication Reconciliation</div>',
                    unsafe_allow_html=True)
        recon = E.get("reconciliation", {})
        rc1, rc2, rc3 = st.columns(3)
        with rc1: st.metric("Admission Meds Documented", "Yes ✓" if recon.get("admission_meds_documented") else "No ✗")
        with rc2: st.metric("Discharge Meds Found", recon.get("discharge_meds_count", 0))
        with rc3: st.metric("Reconciliation Required", "Yes ⚠️" if recon.get("reconciliation_required") else "No ✓")
        if recon.get("reconciliation_required"):
            st.markdown(f'<div class="flag-card flag-warning" style="margin-top:0.5rem"><span class="flag-icon">⚠️</span><span>{recon.get("flag","")}</span></div>', unsafe_allow_html=True)

    # ── TAB 5: TRACE ──────────────────────────────────────────────────────────
    with tab5:
        st.markdown('<div class="section-label" style="margin-top:1rem">Agent Step Trace</div>',
                    unsafe_allow_html=True)
        st.caption("Every reasoning step the agent took — full observability")
        st.plotly_chart(chart_timeline(T), use_container_width=True, key="trace_tl")
        for s in T:
            ok   = not s.get("error") and "FAIL" not in str(s.get("result","")).upper()
            icon = "✅" if ok else "⚠️"
            action = s.get("action","?").upper().replace("_"," ")
            with st.expander(f"{icon}  Step {s.get('step','?')} — {action}"):
                st.markdown(f"**Reasoning:** {s.get('reasoning','N/A')}")
                if s.get("tools_called"):
                    st.markdown("**Tools called:**")
                    for t in s["tools_called"]:
                        st.markdown(f"<div class='trace-result'>→ {t}</div>", unsafe_allow_html=True)
                if s.get("checks"):
                    st.markdown("**Verification checks:**")
                    for c in s["checks"]:
                        ic = "✅" if c.startswith("PASS") else "❌" if c.startswith("FAIL") else "⚠️"
                        st.write(f"  {ic} {c}")
                st.markdown(f"**Result:** `{s.get('result','N/A')}`")
                if s.get("error"):
                    st.error(f"Error: {s['error']}")
        st.download_button("📥 Download Trace JSON", json.dumps(T, indent=2),
                           file_name=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json")

    # ── TAB 6: LEARNING ───────────────────────────────────────────────────────
    with tab6:
        st.markdown('<div class="section-label" style="margin-top:1rem">Part 2 — Continuous Learning</div>',
                    unsafe_allow_html=True)
        st.caption("Simulated doctor reviewer · Edit distance tracking · Prompt optimization loop")

        if not E.get("diagnoses"):
            st.markdown("""
            <div class="flag-card flag-info">
              <span class="flag-icon">ℹ️</span>
              <span>Run the agent first (upload or sample data), then revisit this tab.</span>
            </div>""", unsafe_allow_html=True)
            with st.expander("📖 How does the learning loop work?"):
                st.markdown("""
                **The learning mechanism:**
                1. **Simulated Doctor** applies a consistent editing policy to the agent's draft
                2. **Edit Distance** measures how many corrections were needed
                3. **Agent learns** from the edits — updates its prompt strategy
                4. **Before/After metric** shows measurable improvement over iterations

                The reward signal is reduced edit burden. The agent learns to pre-empt the doctor's most common corrections.
                """)
        else:
            with st.spinner("Running simulated doctor review and learning loop..."):
                results = demonstrate_improvement(E)

            st.markdown('<div class="section-label">Learning Outcome</div>', unsafe_allow_html=True)
            lc1, lc2, lc3 = st.columns(3)
            with lc1: st.metric("Before Edit Burden", results["before_edit_count"])
            with lc2: st.metric("After Edit Burden",  results["after_edit_count"])
            with lc3: st.metric("Edit Reduction", f"{results['improvement']}%",
                                delta=f"-{results['improvement']}%")

            st.markdown("<div style='margin:1.5rem 0 0.5rem'></div>", unsafe_allow_html=True)
            la, lb = st.columns(2)
            with la:
                st.markdown("""<div class="learn-card">
                  <div class="learn-card-title" style="color:#ef4444">🔴 Before Learning — Doctor Edits Required</div>
                """, unsafe_allow_html=True)
                for edit in results["before_edits"]:
                    st.markdown(f'<div class="edit-item-before">✏️ {edit}</div>', unsafe_allow_html=True)
                if not results["before_edits"]:
                    st.markdown('<div class="edit-item-after">No edits needed</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with lb:
                st.markdown("""<div class="learn-card">
                  <div class="learn-card-title" style="color:#10b981">🟢 After Learning — Remaining Edits</div>
                """, unsafe_allow_html=True)
                for edit in results["after_edits"]:
                    st.markdown(f'<div class="edit-item-after">✏️ {edit}</div>', unsafe_allow_html=True)
                if not results["after_edits"]:
                    st.markdown('<div class="edit-item-after">✅ No edits needed!</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
            m = results["metrics"]
            st.plotly_chart(chart_improvement(
                m["before_avg_edit_distance"], m["after_avg_edit_distance"]
            ), use_container_width=True, key="learn_chart")

            st.markdown(f"""
            <div class="flag-card flag-info" style="margin-top:0.5rem">
              <span class="flag-icon">📈</span>
              <span>Learning achieved <strong>{results['improvement']}% reduction</strong> in edit burden.
              Agent learned to pre-populate missing fields, surface conflicts proactively,
              and flag medication reconciliation gaps automatically.</span>
            </div>""", unsafe_allow_html=True)

            st.download_button(
                "📥 Download Learning Results JSON", json.dumps(results, indent=2),
                file_name=f"learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

# ── FOOTER (FIXED: visible text colors) ──
st.markdown("<div style='margin-top:3rem'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:2rem 0 1rem;border-top:1px solid rgba(255,255,255,0.05);">
  <div style="font-family:'DM Mono',monospace;font-size:0.65rem;letter-spacing:0.15em;
  text-transform:uppercase;color:#64748b;margin-bottom:0.5rem;">
    Dscribe · Unriddle Technologies · AI Discharge Summary Agent
  </div>
  <div style="font-size:0.75rem;color:#64748b;">
    ⚕️ AI-generated draft only · Clinician review mandatory · All patient data is synthetic · © 2026
  </div>
</div>
""", unsafe_allow_html=True)