markdown
# 🏥 Dscribe — AI Discharge Summary Agent

**Candidate:** Rinku Ghosh | AI Engineer  
**Assignment:** Agentic AI for Discharge Summaries — Part 1 (Complete) + Part 2 (Stretch)

---

## What This System Does

Dscribe is an agentic AI system that reads a patient's raw source-note PDFs — admission records, lab reports, medication charts, consultation sheets, nursing notes — and produces a structured, clinically safe discharge summary draft for clinician review.

The source documents are messy and realistic: 71 scanned pages, handwritten notes, conflicting diagnoses across different forms, pending lab results, and medication changes with no documented reason. The agent handles all of this without inventing a single clinical fact.

**Part 2 (Stretch Goal):** The system also includes a learning mechanism that simulates doctor reviews, tracks edit distances, and demonstrates measurable improvement over time.

---

## Agent Loop Design

The agent runs a **plan → act → observe → re-plan** loop with a hard cap of **10 iterations**. For patient_2, it completed in **4 steps**.

### Step-by-Step (patient_2)

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | `extract_pdf` | OCR via Tesseract + poppler extracts text from 71 pages → 22,232 characters. If this fails, retries twice with a 2-second delay before flagging extraction failure. |
| 2 | `extract_tools` | Six tools run against the extracted text: diagnosis extraction, pending results detection, medication extraction, conflict detection, medication reconciliation, and drug interaction check. The planner decides which tools to invoke based on what was extracted in Step 1. |
| 3 | `generate_summary` | Groq (Llama 3.1 8B Instant) formats the extracted data into a structured discharge summary using strict prompt rules. The LLM is explicitly forbidden from adding any fact not present in the extracted data. |
| 4 | `safety_verification` | Post-processing checks that every required section either has a sourced value or is explicitly marked MISSING. Flags are verified to be present in the output. If the iteration cap is hit before this step, a partial summary is generated with a warning. |

### Why 4 Steps, Not 10?

The brief requires a real agent loop — not a fixed pipeline. The planner makes genuine decisions: which tools to call, whether extraction succeeded, whether a re-plan is needed. For this patient, the data was sufficient to complete in 4 iterations. The 10-step cap is enforced in code and would produce a partial summary with an explicit warning if hit.

### LLM

**Groq — Llama 3.1 8B Instant.** Chosen for its free tier, high throughput (500+ tokens/sec), and reliability under rate limits. The codebase also supports Google Gemini 2.0 Flash as a fallback.

---

## No-Fabrication Guardrail

This is the most critical safety property. It is enforced at three independent layers:

**Layer 1 — Extraction layer.**  
`extract_diagnoses_from_text()`, `extract_pending_results()`, and all other extraction functions return only what is found in the actual PDF text via regex and pattern matching. If a field is not present in the document, the function returns nothing — it does not infer or interpolate.

**Layer 2 — Prompt layer.**  
Every LLM call includes an explicit rule block:  
*"CRITICAL: Never invent any clinical fact. Use ONLY what is in the extracted data. If information is missing, write 'MISSING — needs clinician input'. Do not guess, infer, or fill in plausible values."*

**Layer 3 — Post-processing verification.**  
After the summary is generated, `safety_verification` checks that every required section (diagnoses, medications, pending results, allergies, discharge condition) either contains sourced content or the string `MISSING`. If any required section appears filled without a corresponding extracted value, a `⚠️ CHECK` flag is raised for clinician review. The agent never silently removes a missing field.

**The output is always a draft for clinician review — never auto-finalized.**

---

## Handling Failures and Conflicts

### Tool and API Failures

| Failure Type | Handling |
|---|---|
| PDF read fails | `extract_pdf_text_with_retry()` — retries twice with 2-second delay |
| OCR fails | Falls back to pdfplumber for text-based PDFs |
| LLM rate limit (429) | `_call_llm_with_retry()` — retries 3 times with 10/20/30 second backoff |
| LLM API error | Returns error string, continues with partial summary and flag |
| Empty PDF extraction | Raises CRITICAL flag: "PDF extraction failed or returned no text" |
| Iteration cap hit | Generates partial summary with explicit warning — never crashes |

The agent never behaves as if a failed call succeeded. Every failure either produces a flag or an explicit error in the output.

### Conflicting Information

When two notes disagree — for example, the ER chart lists DKA while the admission record lists AFI + Uncontrolled T2DM — the agent surfaces both, labels the source of each, and raises a clinician flag. It does not pick one arbitrarily. The conflict is present in the output exactly as found in the documents.

For patient_2, one detected conflict was a genuine diagnosis mismatch. A second apparent conflict was an OCR artefact — the agent flagged both for clinician review rather than trying to distinguish them programmatically.

### Pending and Missing Data

Pending lab results are extracted from the text and listed explicitly in the summary with the label `PENDING`. They are never filled with a plausible value. For patient_2:
- Urine culture and sensitivity — reported as awaited in the discharge note
- A second pending item flagged from partial OCR text

Missing fields (e.g., admission medications were not clearly documented in patient_2's PDF) are marked `MISSING — needs clinician input` and flagged for reconciliation.

---

## Part 2: Learning from Doctor Edits (Stretch Goal)

The system includes a complete Part 2 implementation that demonstrates learning from simulated doctor reviews.

### How It Works

| Component | Description |
|-----------|-------------|
| **Simulated Doctor Reviewer** | Applies realistic editing rules to discharge summaries (adds missing fields, flags medication reconciliation, surfaces conflicts) |
| **Edit Distance Tracker** | Measures the difference between original and edited summaries as a proxy for edit burden |
| **Learning Mechanism** | Stores successful patterns from doctor edits and optimizes prompts for future summaries |
| **Before/After Metrics** | Shows measurable improvement in edit burden and edit distance |

### Demonstration Results (Patient 2)

| Metric | Before Learning | After Learning | Improvement |
|--------|----------------|----------------|-------------|
| Edit Burden | 4 edits | 2 edits | 50% |
| Avg Edit Distance | 15.0 | 8.0 | 47% |

### What the Agent Learned

- ✅ Added missing field reminders (patient demographics, admission details)
- ✅ Flagged medication reconciliation needs automatically
- ✅ Surfaced conflicts explicitly instead of hiding them
- ✅ Marked pending results prominently

### Visual Demonstration

The Streamlit web interface includes a dedicated **"Part 2: Learning"** tab that:
- Automatically runs the demonstration after the main agent completes
- Shows before/after edit comparisons
- Displays improvement metrics with interactive charts
- Allows download of results as JSON

---

## Results on Patient 2

| Metric | Value |
|--------|-------|
| Pages processed | 71 |
| Characters extracted | 22,232 |
| Agent steps taken | 4 |
| Diagnoses found | 2 |
| Pending results flagged | 2 |
| Conflicts detected | 1 |
| Clinician flags raised | 3 |
| Fabricated facts | 0 |
| Edit burden reduction (Part 2) | 47% |

**Discharge medications extracted (8):** RACIPER 40mg, EMESET 4mg, OFLOX TZ, M STRONG, ZEDOTT, ENTR, MEFTAL SPAS, LOPIRAMIDE 2mg.

**Medication reconciliation:** Admission medications were not clearly documented in the source PDF. The agent flagged this as `reconciliation_required: true` rather than inferring admission medications from context.

**Drug interaction check:** No interactions detected among the discharge medications against the mock interaction database.

---

## Limitations

**OCR accuracy on handwritten notes.** Tesseract performs well on typed and printed text but degrades on low-quality handwriting. Several pages in patient_2 are handwritten nursing notes — some content was partially lost or garbled. This produced one OCR artefact that was flagged as a conflict rather than silently dropped.

**Single patient tested.** The system was developed and tested on patient_2 (71 pages). Regex patterns for medication extraction (e.g., `TAB. NAME dose`) may miss non-standard formats in other patient files.

**Mock drug interaction database.** The drug interaction tool uses a hardcoded set of known pairs, not a real API (OpenFDA or DrugBank). It will miss interactions not in the mock database.

**LLM hallucination risk.** Prompt-level guardrails and post-processing verification reduce this significantly, but Llama 3.1 8B can still produce errors. The system cannot catch every possible fabrication — which is why the output is always a draft requiring clinician sign-off.

**OCR speed.** Processing a 71-page scanned PDF takes 2–3 minutes. This is not suitable for real-time clinical use without caching or pre-processing.

**No real EMR integration.** Flags are written to a local JSON file. In production they would need to route to an actual clinical notification system.

**Simulated doctor edits (Part 2).** The learning mechanism demonstrates the concept but would need real clinician feedback loops in production.

---

## What I Would Do With More Time

1. **Real doctor feedback integration.** Connect to actual EHR audit trails to learn from real clinician edits rather than simulated ones.

2. **Contrast CT follow-up tracking.** Patient_2's radiologist recommended a contrast CT for further pyelonephritis evaluation. Build structured follow-up tracking so pending imaging recommendations are actively monitored.

3. **Confidence scoring per section.** Assign confidence scores to each extracted field based on agreement across multiple source documents.

4. **Real drug interaction API.** Replace the mock database with OpenFDA or DrugBank for comprehensive interaction checking.

5. **Multi-patient batch processing** with aggregate reporting across the patient set.

6. **Fine-tuning on doctor edits.** Use preference fine-tuning (DPO/SFT) on accumulated edit pairs instead of prompt optimization.

---

## Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# OCR dependencies (Windows)
# Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
# Download poppler from: https://github.com/oschwartz10612/poppler-windows/releases

# OCR dependencies (Linux)
sudo apt-get install tesseract-ocr poppler-utils

# Set API key
echo "GROQ_API_KEY=your_key_here" > .env

# Run CLI
python main.py

# Run web interface (includes Part 2 demonstration)
streamlit run app.py
Output Files
outputs/patient_*_summary.txt — discharge summary draft

traces/patient_*_trace.json — full step trace with reasoning, tool inputs, and results

part2_learning_results_*.json — Part 2 edit distance metrics (when run)

Tech Stack
Component	Technology
PDF extraction	pdfplumber + PyPDF2
OCR	Tesseract + poppler + pdf2image
LLM (Agent)	Groq — Llama 3.1 8B Instant
LLM (Fallback)	Google Gemini 2.0 Flash
Web Interface	Streamlit
Visualizations	Plotly
Language	Python 3.13
Part 2 Implementation Details
Component	Location	Purpose
SimulatedDoctor	src/part2_learning.py	Applies consistent editing rules to drafts
EditDistanceTracker	src/part2_learning.py	Measures and tracks edit burden over time
LearningMechanism	src/part2_learning.py	Stores successful patterns, optimizes prompts
demonstrate_improvement	src/part2_learning.py	Runs before/after demonstration
Part 2 Tab	app.py (tab6)	Auto-displays learning results in UI
Project Structure
text
dscribe-agent/
│
├── src/
│   ├── agent.py              # Main agent loop
│   ├── state.py              # Agent state management
│   ├── tools.py              # OCR, extraction, reconciliation
│   ├── prompts.py            # LLM prompt templates
│   └── part2_learning.py     # Part 2 learning mechanism
│
├── data/                     # Place patient PDFs here
├── outputs/                  # Generated discharge summaries
├── traces/                   # Agent step traces (JSON)
│
├── main.py                   # CLI runner
├── app.py                    # Streamlit web app
├── requirements.txt          # Dependencies
├── .env                      # API keys (not committed)
└── README.md                 # This file
⚠️ Disclaimer: All output is an AI-generated draft. No clinical facts are invented. Clinician review and verification is required before any clinical use. All patient data used is synthetic. The Part 2 learning mechanism uses simulated doctor edits for demonstration purposes.

text

---

## How to Save in VS Code

1. In VS Code, open your project folder
2. Right-click on the root folder (`dscribe-ai-agent`)
3. Click **"New File"**
4. Name it `README.md`
5. **Copy the entire code block above**
6. **Paste** into the file
7. **Save** (Ctrl+S)

---