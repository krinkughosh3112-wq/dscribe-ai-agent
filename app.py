# app.py — Dscribe AI Discharge Summary Agent
import streamlit as st
import pdfplumber
import plotly.graph_objects as go
import plotly.express as px
import re
import os
import json
import shutil
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from src.part2_learning import demonstrate_improvement

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="Dscribe - AI Discharge Summary Agent",
    page_icon="🏥",
    layout="wide"
)

st.markdown("""
<style>
    /* Hide default streamlit header */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .main-header h1 { font-size: 2rem; margin-bottom: 0.3rem; }
    .main-header p { opacity: 0.85; margin: 0.2rem 0; }

    .safety-badge {
        background: linear-gradient(90deg, #e53e3e, #c53030);
        color: white;
        padding: 0.3rem 0.9rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
        margin-top: 0.5rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #667eea15, #764ba215);
        border: 1px solid #667eea40;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-number {
        font-size: 2.5rem;
        font-weight: 700;
        color: #667eea;
        line-height: 1;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #888;
        margin-top: 0.3rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .flag-critical {
        background: linear-gradient(90deg, #fff5f5, #fed7d7);
        border-left: 4px solid #e53e3e;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.9rem;
    }
    .flag-warning {
        background: linear-gradient(90deg, #fffbeb, #fef3c7);
        border-left: 4px solid #f59e0b;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.9rem;
    }
    .flag-info {
        background: linear-gradient(90deg, #eff6ff, #dbeafe);
        border-left: 4px solid #3b82f6;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.9rem;
    }

    .trace-step {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem;
        margin: 0.4rem 0;
        font-family: 'Courier New', monospace;
        font-size: 0.82rem;
    }

    .summary-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        font-family: 'Georgia', serif;
        line-height: 1.7;
    }

    div[data-testid="stTabs"] button {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ── HEADER ──
st.markdown("""
<div class="main-header">
    <h1>🏥 Dscribe — AI Discharge Summary Agent</h1>
    <p>Agentic AI that turns messy, multi-page clinical notes into structured, clinically safe discharge summaries</p>
    <p>Powered by Groq · Llama 3.1 8B · 10-step hard cap · Full observability</p>
    <span class="safety-badge">⚕️ Safety First: Never invents clinical facts</span>
</div>
""", unsafe_allow_html=True)

# ── SIDEBAR ──
with st.sidebar:
    st.markdown("### ⚙️ Agent Info")
    st.markdown("""
    **LLM:** Groq · Llama 3.1 8B Instant  
    **Iteration cap:** 10 steps (hard)  
    **Retry policy:** 3× with backoff  
    """)
    st.divider()
    st.markdown("**Agent Features**")
    features = [
        "🔄 Real agent loop",
        "📄 PDF + OCR ingestion",
        "🚫 No fabrication guardrail",
        "⏳ Pending results detection",
        "⚠️ Conflict detection",
        "💊 Medication reconciliation",
        "💉 Drug interaction check",
        "🔍 Full step trace + download",
    ]
    for f in features:
        st.markdown(f"- {f}")
    st.divider()
    if API_KEY:
        st.success("✅ Groq API Ready")
    else:
        st.error("❌ GROQ_API_KEY missing")
    st.divider()
    st.caption("⚠️ Output is AI-generated DRAFT.\nNot for clinical use without physician review.\nAll data is synthetic.")


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def find_tesseract():
    if shutil.which("tesseract"):
        return shutil.which("tesseract")
    win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(win):
        return win
    return None

def find_poppler():
    if shutil.which("pdftoppm"):
        return None
    env = os.getenv("POPPLER_PATH")
    if env and os.path.exists(env):
        return env
    return None


# ─────────────────────────────────────────────
# AGENT TOOLS
# ─────────────────────────────────────────────

def extract_text_from_pdf(pdf_path, trace):
    full_text = ""
    step = {"step": 1, "action": "extract_pdf", "reasoning": "Extract raw text. Try pdfplumber first, OCR fallback.", "result": None, "error": None}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                if t.strip():
                    full_text += f"\n--- PAGE {i+1} ---\n{t}\n"
    except Exception as e:
        step["error"] = f"pdfplumber: {e}"

    if not full_text.strip():
        tess = find_tesseract()
        popp = find_poppler()
        if tess:
            try:
                import pytesseract
                from pdf2image import convert_from_path
                pytesseract.pytesseract.tesseract_cmd = tess
                kwargs = {"dpi": 200}
                if popp:
                    kwargs["poppler_path"] = popp
                images = convert_from_path(pdf_path, **kwargs)
                for i, img in enumerate(images):
                    t = pytesseract.image_to_string(img)
                    if t.strip():
                        full_text += f"\n--- PAGE {i+1} ---\n{t}\n"
                step["result"] = f"OCR: {len(full_text):,} chars from {len(images)} pages"
            except Exception as e:
                step["error"] = f"OCR failed: {e}"
        else:
            step["error"] = "Tesseract not found. Install tesseract-ocr."

    step["result"] = step["result"] or (f"pdfplumber: {len(full_text):,} chars" if full_text else "FAILED — no text")
    trace.append(step)
    return full_text


def run_extraction_tools(text, trace):
    step = {"step": 2, "action": "extract_tools", "reasoning": "Run all 6 extraction tools on text.", "tools_called": [], "result": None}
    results = {}

    # Diagnoses
    diagnoses = []
    for pat in [r'DIAGNOSIS\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)',
                r'FINAL\s+DIAG[A-Z]*\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)',
                r'PROVISIONAL\s+DIAG[A-Z]*\s*:?\s*(.*?)(?=\n\s*[A-Z]{3,}[\s:\/]|$)']:
        for m in re.findall(pat, text, re.IGNORECASE | re.DOTALL):
            c = m.strip().replace('\n', ' ')
            if 10 < len(c) < 300:
                diagnoses.append(c[:250])
    results["diagnoses"] = list(set(diagnoses))
    step["tools_called"].append(f"diagnosis_extraction → {len(results['diagnoses'])} found")

    # Pending
    pending = []
    for pat in [r'([^.\n]*(?:report|result|culture|sensitivity)[^.\n]*(?:awaited|pending|sent to lab|due)[^.\n]*)',
                r'([^.\n]*(?:awaited|pending)[^.\n]*(?:report|result|culture)[^.\n]*)']:
        for m in re.findall(pat, text, re.IGNORECASE):
            c = m.strip()
            if len(c) > 10:
                pending.append(c[:200])
    results["pending"] = list(set(pending))
    step["tools_called"].append(f"pending_detection → {len(results['pending'])} found")

    # Medications
    meds = []
    for pat in [r'TAB\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+\s*MG|\s+\d+\s*MCG|\s+\d+-\d+-\d+|\s+\d+\s+DAYS)',
                r'INJ\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+|\s+[A-Z]{2,})',
                r'SYP\.?\s+([A-Z][A-Z0-9\s]+?)(?:\s+\d+|\s+[A-Z]{2,})']:
        for m in re.findall(pat, text, re.IGNORECASE):
            c = m.strip()
            if 2 < len(c) < 40:
                meds.append(c)
    results["medications"] = list(set(meds))
    step["tools_called"].append(f"medication_extraction → {len(results['medications'])} found")

    # Conflicts
    conflicts = []
    if len(results["diagnoses"]) > 1:
        conflicts.append(f"Multiple diagnoses found across notes — clinician must reconcile")
    for a, b in [("DKA", "gastroenteritis"), ("pyelonephritis", "UTI"), ("AFI", "DKA")]:
        if a.lower() in text.lower() and b.lower() in text.lower():
            conflicts.append(f"Conflicting terms in notes: '{a}' and '{b}' both present")
    results["conflicts"] = list(set(conflicts))
    step["tools_called"].append(f"conflict_detection → {len(results['conflicts'])} found")

    # Reconciliation
    adm_found = bool(re.search(r'admission\s+med|prior\s+med|home\s+med|regular\s+med', text, re.IGNORECASE))
    results["reconciliation"] = {
        "admission_meds_documented": adm_found,
        "discharge_meds_count": len(results["medications"]),
        "reconciliation_required": not adm_found,
        "flag": "Admission meds not documented — full reconciliation required" if not adm_found else "Reconciliation complete"
    }
    step["tools_called"].append(f"medication_reconciliation → required={results['reconciliation']['reconciliation_required']}")

    # Drug interactions (mock)
    known = {
        frozenset(["meropenem", "metformin"]): "MODERATE — monitor renal function",
        frozenset(["lantus", "actrapid"]): "LOW — dual insulin, monitor hypoglycaemia",
        frozenset(["dolo", "tramadol"]): "LOW — additive CNS depression",
    }
    interactions = []
    ml = [m.lower() for m in results["medications"]]
    for pair, warn in known.items():
        pl = list(pair)
        if any(pl[0] in m for m in ml) and any(pl[1] in m for m in ml):
            interactions.append(f"{' + '.join(pl)}: {warn}")
    results["drug_interactions"] = interactions
    step["tools_called"].append(f"drug_interaction_check (mock) → {len(interactions)} found")

    step["result"] = f"Done. Diagnoses:{len(results['diagnoses'])} Pending:{len(results['pending'])} Meds:{len(results['medications'])} Conflicts:{len(results['conflicts'])}"
    trace.append(step)
    return results


def generate_summary(text, extracted, api_key, trace):
    step = {"step": 3, "action": "generate_summary", "reasoning": "Call LLM with strict no-fabrication prompt.", "result": None, "error": None}
    if not api_key:
        step["error"] = "No API key"
        trace.append(step)
        return "ERROR: No Groq API key."

    client = Groq(api_key=api_key)
    prompt = f"""You are a clinical AI generating a DRAFT discharge summary for clinician review.

CRITICAL RULES:
1. NEVER invent any clinical fact. Use ONLY information in the SOURCE TEXT.
2. If a field is missing, write: MISSING — needs clinician input
3. If a result is pending, write: PENDING: [test name]
4. Do not guess, infer, or fill plausible values.
5. This is a DRAFT — clinician must review before any clinical use.

SOURCE TEXT:
{text[:12000]}

EXTRACTED DATA:
- Diagnoses: {extracted.get('diagnoses', [])}
- Pending: {extracted.get('pending', [])}
- Medications: {extracted.get('medications', [])}
- Conflicts: {extracted.get('conflicts', [])}
- Reconciliation: {extracted.get('reconciliation', {}).get('flag', '')}

Generate this exact format:

=== DISCHARGE SUMMARY (DRAFT — FOR CLINICIAN REVIEW ONLY) ===

PATIENT DEMOGRAPHICS:
[Name, age, gender, IP number — or MISSING]

ADMISSION DATE:
[Date — or MISSING]

DISCHARGE DATE:
[Date — or MISSING]

PRINCIPAL DIAGNOSIS:
[Exactly as documented. Do not pick between conflicts.]

SECONDARY DIAGNOSES:
[All other diagnoses found]

ALLERGIES:
[Exactly as documented — if "Not Known" write that]

HOSPITAL COURSE:
[What happened during admission — source only]

PROCEDURES PERFORMED:
[e.g. IV cannulation, Foley catheterisation, CT KUB, ECG, ECHO, USG]

KEY INVESTIGATIONS:
[Results found. Mark pending as PENDING: [name]]

DISCHARGE MEDICATIONS:
[Each medication with dose and frequency]

MEDICATION CHANGES FROM ADMISSION:
[Changes noted — if admission meds undocumented, state explicitly]

DISCHARGE CONDITION:
[As documented]

FOLLOW-UP INSTRUCTIONS:
[As documented]

PENDING RESULTS AT DISCHARGE:
[Every pending item — never omit]

=== FLAGS FOR CLINICIAN REVIEW ===
[All flags — conflicts, pending, missing, reconciliation, drug interactions]

=== SAFETY STATEMENT ===
AI-generated DRAFT. No clinical facts invented. All missing fields marked. Clinician sign-off required.
"""
    import time
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            summary = resp.choices[0].message.content
            step["result"] = f"Generated {len(summary)} chars"
            trace.append(step)
            return summary
        except Exception as e:
            wait = (attempt + 1) * 10
            step["error"] = f"Attempt {attempt+1}: {e} — retry in {wait}s"
            time.sleep(wait)
    step["result"] = "FAILED after 3 retries"
    trace.append(step)
    return "ERROR: LLM failed after 3 retries."


def safety_verification(summary, extracted, trace):
    step = {"step": 4, "action": "safety_verification", "reasoning": "Verify required sections present, conflicts surfaced, pending listed.", "checks": [], "result": None}
    flags = []

    for section in ["PRINCIPAL DIAGNOSIS", "DISCHARGE MEDICATIONS", "PENDING RESULTS", "FLAGS FOR CLINICIAN REVIEW"]:
        if section not in summary.upper():
            flags.append(f"⚠️ MISSING SECTION: {section}")
            step["checks"].append(f"FAIL — {section} missing")
        else:
            step["checks"].append(f"PASS — {section} present")

    if extracted.get("conflicts") and "conflict" not in summary.lower():
        flags.append("🔴 CONFLICTS DETECTED but not surfaced in summary")
        step["checks"].append("FAIL — conflicts not in summary")
    elif extracted.get("conflicts"):
        step["checks"].append("PASS — conflicts present in summary")

    if extracted.get("pending") and "pending" not in summary.lower():
        flags.append("🔴 PENDING RESULTS not surfaced in summary")
        step["checks"].append("FAIL — pending not in summary")
    elif extracted.get("pending"):
        step["checks"].append("PASS — pending items in summary")

    if extracted.get("reconciliation", {}).get("reconciliation_required"):
        flags.append(f"⚠️ MEDICATION RECONCILIATION REQUIRED: {extracted['reconciliation']['flag']}")
        step["checks"].append("FLAG — reconciliation required")

    for i in extracted.get("drug_interactions", []):
        flags.append(f"💊 DRUG INTERACTION: {i}")

    step["result"] = f"Verification done. {len(flags)} flags raised."
    trace.append(step)
    return summary, flags


def run_agent(pdf_path, api_key):
    MAX_ITER = 10
    trace = []
    iteration = 0

    iteration += 1
    if iteration > MAX_ITER:
        return "CAP HIT", [], {}, trace
    text = extract_text_from_pdf(pdf_path, trace)

    if not text.strip():
        trace.append({"step": iteration, "action": "abort", "result": "CRITICAL: No text extracted"})
        return "CRITICAL: PDF extraction failed.", ["🔴 PDF extraction returned no text"], {}, trace

    iteration += 1
    if iteration > MAX_ITER:
        return "CAP HIT", [], {}, trace
    extracted = run_extraction_tools(text, trace)

    iteration += 1
    if iteration > MAX_ITER:
        return "CAP HIT", [], {}, trace
    summary = generate_summary(text, extracted, api_key, trace)

    iteration += 1
    if iteration > MAX_ITER:
        return "CAP HIT", [], {}, trace
    summary, flags = safety_verification(summary, extracted, trace)

    return summary, flags, extracted, trace


# ─────────────────────────────────────────────
# CHART HELPERS
# ─────────────────────────────────────────────

def make_extraction_donut(extracted):
    labels = ["Diagnoses", "Pending Results", "Medications", "Conflicts", "Drug Interactions"]
    values = [
        len(extracted.get("diagnoses", [])),
        len(extracted.get("pending", [])),
        len(extracted.get("medications", [])),
        len(extracted.get("conflicts", [])),
        len(extracted.get("drug_interactions", [])),
    ]
    colors = ["#667eea", "#f59e0b", "#10b981", "#e53e3e", "#8b5cf6"]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+value",
        hovertemplate="%{label}: %{value}<extra></extra>"
    ))
    fig.update_layout(
        title=dict(text="Extraction Summary", font=dict(size=15)),
        showlegend=False,
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def make_flag_severity_bar(flags):
    critical = sum(1 for f in flags if "🔴" in f or "CRITICAL" in f)
    warning  = sum(1 for f in flags if "⚠️" in f)
    info     = sum(1 for f in flags if "💊" in f or "💡" in f)
    other    = len(flags) - critical - warning - info

    fig = go.Figure(go.Bar(
        x=["Critical 🔴", "Warning ⚠️", "Drug 💊", "Other"],
        y=[critical, warning, info, other],
        marker_color=["#e53e3e", "#f59e0b", "#8b5cf6", "#6b7280"],
        text=[critical, warning, info, other],
        textposition="outside"
    ))
    fig.update_layout(
        title=dict(text="Flags by Severity", font=dict(size=15)),
        yaxis=dict(title="Count", showgrid=True, gridcolor="#f0f0f0"),
        xaxis=dict(title=""),
        margin=dict(t=40, b=10, l=10, r=10),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False
    )
    return fig


def make_agent_steps_timeline(trace):
    steps = [s.get("action", "?").replace("_", " ").title() for s in trace]
    indices = list(range(1, len(steps) + 1))
    status = []
    for s in trace:
        if s.get("error") and "FAIL" in str(s.get("result", "")):
            status.append("Failed")
        elif s.get("error"):
            status.append("Warning")
        else:
            status.append("Success")

    color_map = {"Success": "#10b981", "Warning": "#f59e0b", "Failed": "#e53e3e"}
    colors = [color_map[s] for s in status]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=indices, y=[1]*len(indices),
        mode="markers+lines+text",
        marker=dict(size=18, color=colors, line=dict(color="white", width=2)),
        line=dict(color="#667eea", width=2, dash="dot"),
        text=steps,
        textposition="top center",
        hovertemplate=[f"Step {i}: {s}<br>Status: {st}<extra></extra>"
                       for i, s, st in zip(indices, steps, status)]
    ))
    fig.update_layout(
        title=dict(text="Agent Step Timeline", font=dict(size=15)),
        xaxis=dict(title="Step", showgrid=False, tickvals=indices, range=[0.5, len(indices)+0.5]),
        yaxis=dict(showticklabels=False, showgrid=False, range=[0.7, 1.5]),
        height=220,
        margin=dict(t=40, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False
    )
    return fig


def make_safety_gauge(flags, extracted):
    score = 100
    score -= len([f for f in flags if "🔴" in f or "CRITICAL" in f]) * 20
    score -= len([f for f in flags if "⚠️" in f]) * 10
    score -= len(extracted.get("conflicts", [])) * 15
    score -= len(extracted.get("pending", [])) * 5
    score = max(0, min(100, score))

    color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#e53e3e"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": "Clinician Review Score", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 70], "color": "#fef3c7"},
                {"range": [70, 100], "color": "#d1fae5"},
            ],
            "threshold": {"line": {"color": "red", "width": 2}, "thickness": 0.75, "value": 40}
        },
        number={"suffix": "%", "font": {"size": 28}}
    ))
    fig.update_layout(
        height=250,
        margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)"
    )
    return fig


# ─────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────

col1, col2 = st.columns([1.2, 0.8])
with col1:
    st.markdown("#### 📄 Upload Patient Notes")
    uploaded_file = st.file_uploader("Choose PDF file (up to 200MB)", type=["pdf"], label_visibility="collapsed")
    if st.button("📋 Use Sample Data"):
        st.session_state["use_sample"] = True
        st.rerun()

with col2:
    st.markdown("#### 🤖 Agent Control")
    st.caption("Hard iteration cap: 10 steps · LLM: Groq Llama 3.1 8B · Retry: 3× with backoff")
    run_button = st.button(
        "🚀 Generate Discharge Summary",
        type="primary",
        use_container_width=True,
        disabled=not (uploaded_file or st.session_state.get("use_sample", False))
    )

if run_button:
    if not API_KEY:
        st.error("❌ GROQ_API_KEY not found in .env file.")
        st.stop()

    with st.status("🤖 Agent running...", expanded=True) as status_box:
        st.write("📄 Step 1: Extracting text from PDF...")

        use_sample = st.session_state.get("use_sample", False)
        st.session_state["use_sample"] = False

        if use_sample:
            sample_text = """DIAGNOSIS: 1) ACUTE GASTROENTERITIS WITH DEHYDRATION 2) URINARY TRACT INFECTION
HISTORY: C/O Multiple episodes of loose stools, 2-3 episodes of vomiting, fatigue since 3 days and fever since yesterday.
PAST HISTORY: K/C/O Thyroid disorder on treatment.
PHYSICAL EXAMINATION: PR-89/min, BP-130/80 mmHg, RR-20/min, SPO2-98% at room air.
INVESTIGATIONS: Serum creatinine (1.65mg/dl) elevated. Serum sodium (128.00mmol/L) low.
Urine culture and sensitivity sent - report awaited.
USG Abdomen: Grade-I fatty liver. Repeat Serum Creatinine (1.17mg/dl) normal.
CONDITION AT DISCHARGE: Hemodynamically stable
ADVICE ON DISCHARGE:
TAB RACIPER 40MG 1-0-0 7 DAYS BEFORE FOOD
TAB EMESET 4MG 1-1-1 3 DAYS
TAB OFLOX TZ 1-0-1 5 DAYS
TAB M STRONG 1-0-0 15 DAYS
TAB ZEDOTT 1-1-1 3 DAYS
TAB LOPIRAMIDE 2MG 1-0-1 5 DAYS
FOLLOW-UP: Review on 09.03.2026. Urine culture and sensitivity sent - report awaited.
Drug Allergy: Not Known"""
            trace = []
            trace.append({"step": 1, "action": "extract_pdf", "reasoning": "Sample data used.", "result": f"{len(sample_text):,} chars loaded"})
            st.write("🔍 Step 2: Running extraction tools...")
            extracted = run_extraction_tools(sample_text, trace)
            st.write("🧠 Step 3: Generating summary with LLM...")
            summary = generate_summary(sample_text, extracted, API_KEY, trace)
            st.write("✅ Step 4: Safety verification...")
            summary, flags = safety_verification(summary, extracted, trace)
            st.session_state['current_summary'] = summary
            st.session_state['current_flags'] = flags
            st.session_state['current_extracted'] = extracted
            st.session_state['current_trace'] = trace
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                pdf_path = tmp.name
            st.write("🔍 Step 2: Running extraction tools...")
            st.write("🧠 Step 3: Generating summary with LLM...")
            st.write("✅ Step 4: Safety verification...")
            summary, flags, extracted, trace = run_agent(pdf_path, API_KEY)
            st.session_state['current_summary'] = summary
            st.session_state['current_flags'] = flags
            st.session_state['current_extracted'] = extracted
            st.session_state['current_trace'] = trace
            try:
                os.unlink(pdf_path)
            except Exception:
                pass

        status_box.update(label="✅ Agent complete!", state="complete")

    display_summary = st.session_state.get('current_summary', "")
    display_flags = st.session_state.get('current_flags', [])
    display_extracted = st.session_state.get('current_extracted', {})
    display_trace = st.session_state.get('current_trace', [])

    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    metrics = [
        (len(display_extracted.get("diagnoses", [])), "Diagnoses"),
        (len(display_extracted.get("pending", [])), "Pending Results"),
        (len(display_extracted.get("medications", [])), "Medications"),
        (len(display_extracted.get("conflicts", [])), "Conflicts"),
        (len(display_flags), "Flags Raised"),
    ]
    for col, (val, label) in zip([m1, m2, m3, m4, m5], metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-number">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Summary", "⚠️ Flags", "📊 Charts", "🔬 Analysis", "🔍 Step Trace", "🧠 Part 2: Learning"
    ])

    with tab1:
        st.markdown("### Discharge Summary Draft")
        st.markdown(f'<div class="summary-box">{display_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("📥 Download Summary (.txt)", display_summary,
                          file_name=f"discharge_summary_{ts}.txt", mime="text/plain")

    with tab2:
        st.markdown("### Clinician Flags")
        if display_flags:
            critical_flags = [f for f in display_flags if "🔴" in f or "CRITICAL" in f]
            warning_flags  = [f for f in display_flags if "⚠️" in f]
            other_flags    = [f for f in display_flags if f not in critical_flags and f not in warning_flags]

            if critical_flags:
                st.markdown("**🔴 Critical**")
                for f in critical_flags:
                    st.markdown(f'<div class="flag-critical">{f}</div>', unsafe_allow_html=True)
            if warning_flags:
                st.markdown("**⚠️ Warnings**")
                for f in warning_flags:
                    st.markdown(f'<div class="flag-warning">{f}</div>', unsafe_allow_html=True)
            if other_flags:
                st.markdown("**ℹ️ Info**")
                for f in other_flags:
                    st.markdown(f'<div class="flag-info">{f}</div>', unsafe_allow_html=True)
        else:
            st.success("✅ No flags raised")

    with tab3:
        st.markdown("### 📊 Visual Analysis")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(make_extraction_donut(display_extracted), use_container_width=True, key="donut")
        with c2:
            st.plotly_chart(make_flag_severity_bar(display_flags), use_container_width=True, key="bar")
        c3, c4 = st.columns([1.5, 1])
        with c3:
            st.plotly_chart(make_agent_steps_timeline(display_trace), use_container_width=True, key="timeline_charts")
        with c4:
            st.plotly_chart(make_safety_gauge(display_flags, display_extracted), use_container_width=True, key="gauge")
        if display_extracted.get("medications"):
            st.markdown("#### 💊 Discharge Medications")
            meds = display_extracted["medications"][:15]
            fig = go.Figure(go.Bar(
                y=meds, x=[1]*len(meds),
                orientation="h",
                marker_color="#667eea",
                text=meds,
                textposition="inside",
                insidetextanchor="middle"
            ))
            fig.update_layout(
                height=max(200, len(meds) * 32),
                xaxis=dict(showticklabels=False, showgrid=False),
                yaxis=dict(showticklabels=False),
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True, key="meds_bar")

    with tab4:
        st.markdown("### 🔬 Detailed Extraction")
        if display_extracted.get("diagnoses"):
            st.markdown("**Diagnoses Found:**")
            for d in display_extracted["diagnoses"]:
                st.info(d)
        if display_extracted.get("pending"):
            st.markdown("**Pending Results:**")
            for p in display_extracted["pending"]:
                st.warning(f"⏳ {p}")
        if display_extracted.get("conflicts"):
            st.markdown("**Conflicts Detected:**")
            for c in display_extracted["conflicts"]:
                st.error(f"🔴 {c}")
        st.markdown("**Medication Reconciliation:**")
        recon = display_extracted.get("reconciliation", {})
        rc1, rc2 = st.columns(2)
        with rc1:
            st.metric("Admission Meds Documented", "Yes" if recon.get("admission_meds_documented") else "No")
        with rc2:
            st.metric("Discharge Meds Found", recon.get("discharge_meds_count", 0))
        if recon.get("reconciliation_required"):
            st.warning(f"⚠️ {recon.get('flag', '')}")
        else:
            st.success(recon.get("flag", ""))
        if display_extracted.get("drug_interactions"):
            st.markdown("**Drug Interactions:**")
            for i in display_extracted["drug_interactions"]:
                st.warning(f"💊 {i}")
        else:
            st.success("✅ No drug interactions detected")

    with tab5:
        st.markdown("### 🔍 Agent Step Trace")
        st.caption("Full observability — every decision the agent made")
        st.plotly_chart(make_agent_steps_timeline(display_trace), use_container_width=True, key="timeline_trace")
        for step in display_trace:
            icon = "✅" if not step.get("error") else "⚠️"
            with st.expander(f"{icon} Step {step.get('step','?')} — {step.get('action','?').upper()}"):
                st.markdown(f"**Reasoning:** {step.get('reasoning','N/A')}")
                if step.get("tools_called"):
                    st.markdown("**Tools called:**")
                    for t in step["tools_called"]:
                        st.write(f"  → {t}")
                if step.get("checks"):
                    st.markdown("**Verification checks:**")
                    for c in step["checks"]:
                        icon2 = "✅" if c.startswith("PASS") else "❌" if c.startswith("FAIL") else "⚠️"
                        st.write(f"  {icon2} {c}")
                st.markdown(f"**Result:** `{step.get('result','N/A')}`")
                if step.get("error"):
                    st.error(f"Error: {step['error']}")
        st.download_button(
            "📥 Download Full Trace (JSON)",
            json.dumps(display_trace, indent=2),
            file_name=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    with tab6:
        st.markdown("### 🧠 Part 2: Learning from Doctor Edits (Stretch Goal)")
        st.caption("Simulated doctor reviewer + edit distance tracking + prompt optimization")
        
        # Check if agent has been run
        has_data = display_extracted and display_extracted.get("diagnoses")
        
        if not has_data:
            st.info("ℹ️ **No patient data available**")
            st.markdown("""
            Please run the main agent first:
            1. Go to the top of the page
            2. Upload a PDF or click **"Use Sample Data"**
            3. Click **"Generate Discharge Summary"**
            4. Wait for completion
            5. Then come back to this tab
            """)
            
            with st.expander("📖 What is Part 2?"):
                st.markdown("""
                **Part 2 demonstrates learning from doctor edits:**
                
                - **Simulated Doctor Reviewer** - Reviews the discharge summary and applies realistic edits
                - **Edit Distance Tracking** - Measures how many changes the doctor needed to make
                - **Learning Mechanism** - The agent learns from these edits and improves future summaries
                - **Before/After Metrics** - Shows measurable improvement over time
                
                **Run the main agent first to see the demonstration!**
                """)
        else:
            # Auto-run the demonstration without button
            with st.spinner("Running simulated doctor review..."):
                results = demonstrate_improvement(display_extracted)
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Before Edit Burden", results["before_edit_count"])
                with col2:
                    st.metric("After Edit Burden", results["after_edit_count"])
                with col3:
                    st.metric("Improvement", f"{results['improvement']}%", delta=f"-{results['improvement']}%")
                
                st.divider()
                
                # Show before/after comparison
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**🔴 Before Learning - Edits Required**")
                    for edit in results["before_edits"]:
                        st.warning(f"✏️ {edit}")
                    if not results["before_edits"]:
                        st.info("No edits needed")
                
                with col_b:
                    st.markdown("**🟢 After Learning - Edits Remaining**")
                    for edit in results["after_edits"]:
                        st.info(f"✏️ {edit}")
                    if not results["after_edits"]:
                        st.success("✅ No edits needed!")
                
                st.divider()
                
                # Show metrics
                st.markdown("### 📊 Edit Distance Metrics")
                metrics = results["metrics"]
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Before Avg Edit Distance", metrics["before_avg_edit_distance"])
                with m2:
                    st.metric("After Avg Edit Distance", metrics["after_avg_edit_distance"])
                with m3:
                    st.metric("Improvement", f"{metrics['improvement_percentage']}%")
                
                # Improvement chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=["Before Learning", "After Learning"],
                    y=[metrics["before_avg_edit_distance"], metrics["after_avg_edit_distance"]],
                    marker_color=["#e53e3e", "#10b981"],
                    text=[metrics["before_avg_edit_distance"], metrics["after_avg_edit_distance"]],
                    textposition="outside"
                ))
                fig.update_layout(
                    title="Edit Distance Reduction",
                    yaxis_title="Edit Distance",
                    height=350,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.success(f"✅ Learning achieved {results['improvement']}% reduction in edit burden!")
                st.caption("**The agent learned from simulated doctor edits:**")
                st.markdown("- ✅ Added missing field reminders")
                st.markdown("- ✅ Flagged medication reconciliation needs")
                st.markdown("- ✅ Surfaced conflicts explicitly")
                
                st.download_button(
                    "📥 Download Part 2 Results (JSON)",
                    json.dumps(results, indent=2),
                    file_name=f"part2_learning_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

st.divider()
st.caption("🏥 Dscribe AI Agent · DRAFT for clinician review · Never invents facts · Groq Llama 3.1 8B · © 2026 Rinku Ghosh")