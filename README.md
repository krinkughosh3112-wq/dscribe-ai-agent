# 🏥 Dscribe — AI Discharge Summary Agent

**Candidate:** Rinku Ghosh | AI Engineer  
**Assignment:** Agentic AI for Discharge Summaries — Part 1 (Complete) + Part 2 (Complete)

---

## Screenshots

### Main Interface
![Main Interface](screenshots/Screenshot%20(129).png)

### Discharge Summary Output
![Discharge Summary Output](screenshots/Screenshot%20(130).png)

---

## What This System Does

Dscribe is an agentic AI system that reads a patient's raw source-note PDFs — admission records, lab reports, medication charts, consultation sheets, nursing notes — and produces a structured, clinically safe discharge summary draft for clinician review.

The source documents are messy and realistic: multi-page scanned documents, handwritten notes, conflicting diagnoses across different forms, pending lab results, and medication changes with no documented reason. The agent handles all of this without inventing a single clinical fact.

Part 2 adds a complete learning mechanism: a simulated doctor reviewer applies a consistent editing policy to drafts, edit distance is measured as the reward signal, and accumulated corrections are injected into future prompts — producing measurable improvement over iterations.

---

## Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# OCR dependencies (Linux)
sudo apt-get install tesseract-ocr poppler-utils

# OCR dependencies (Windows)
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# Poppler:   https://github.com/oschwartz10612/poppler-windows/releases
# Set POPPLER_PATH env var if not on system PATH

# Add API key
echo "GROQ_API_KEY=your_key_here" > .env

# Run web interface
streamlit run app.py
```

Output files:
- `outputs/discharge_summary_*.txt` — discharge summary draft
- `traces/trace_*.json` — full agent step trace
- `outputs/learning_*.json` — Part 2 edit distance metrics

---

## Agent Loop Design

The agent runs a **plan → act → observe → re-plan** loop with a hard cap of **10 iterations**. For patient_2, it completed in **4 steps**.

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | `extract_pdf` | OCR via Tesseract + poppler extracts text from 71 pages → 22,232 characters. Retries twice with 2-second delay on failure. Falls back to pdfplumber for text-based PDFs. |
| 2 | `extract_tools` | Six tools run against extracted text: diagnosis extraction, pending results detection, medication extraction, conflict detection, medication reconciliation, drug interaction check. Planner decides which tools based on what Step 1 returned. |
| 3 | `generate_summary` | Groq (Llama 3.1 8B Instant) formats extracted data into structured discharge summary with strict no-fabrication prompt. Temperature 0.1 for determinism. |
| 4 | `safety_verification` | Post-processing checks every required section has a sourced value or explicit MISSING marker. Conflicts and pending items verified to appear in output. Flags raised for anything missing. |

**Why 4 steps, not 10?** The brief requires a real agent loop — not a fixed pipeline. The planner makes genuine decisions at each step. For patient_2, data was sufficient to complete in 4 iterations. The 10-step hard cap is enforced in code — hitting it produces a partial summary with an explicit warning, never a crash or silent failure.

**LLM:** Groq — Llama 3.1 8B Instant. Chosen for free tier availability, high throughput (500+ tokens/sec), and reliability under rate limits. Gemini 2.0 Flash supported as fallback.

---

## No-Fabrication Guardrail

The most critical safety property. Enforced at three independent layers:

**Layer 1 — Extraction layer.**
All extraction functions return only what is found in the actual PDF text via regex and pattern matching. If a field is absent from the document, nothing is returned — no inference, no interpolation.

**Layer 2 — Prompt layer.**
Every LLM call includes an explicit rule block:
> *"CRITICAL: Never invent any clinical fact. Use ONLY what is in the extracted data. If information is missing, write 'MISSING — needs clinician input'. Do not guess, infer, or fill in plausible values."*

**Layer 3 — Post-processing verification.**
`safety_verification` checks every required section contains either sourced content or the string `MISSING`. Any section that appears filled without a corresponding extracted value raises a `⚠️ CHECK` flag.

The output is always a draft for clinician review — never auto-finalized.

---

## Handling Failures and Conflicts

### Failures

| Failure Type | Handling |
|--------------|----------|
| PDF read fails | Retries twice with 2-second delay |
| OCR fails | Falls back to pdfplumber |
| LLM rate limit (429) | Retries 3 times with 10/20/30 second backoff |
| LLM API error | Returns error string, continues with partial summary and flag |
| Empty PDF extraction | Raises CRITICAL flag — agent aborts safely |
| Iteration cap hit | Partial summary with explicit warning — never crashes |

### Conflicting Information

When two notes disagree the agent surfaces both, labels the source of each, and raises a clinician flag. It does not pick one arbitrarily. For patient_2, one conflict was a genuine diagnosis mismatch (DKA vs AFI + Uncontrolled T2DM across notes). A second was an OCR artefact. Both were flagged.

### Pending and Missing Data

Pending lab results are listed with the label `PENDING` — never filled with plausible values. Missing fields are marked `MISSING — needs clinician input` and flagged for reconciliation.

---

## Part 2 — Learning from Doctor Edits

### Design

| Component | Implementation |
|-----------|---------------|
| Simulated doctor reviewer | Applies a consistent hidden editing policy: adds mandatory safety headers, clarifies MISSING fields with specific action items, makes PENDING labels explicit with action required notes, adds clinician review signature block |
| Reward signal | Normalised edit distance between agent draft and doctor-edited version. Less editing = higher reward. Score = 1 − (edit_distance / max_length) |
| Learning mechanism | Correction memory — accumulated edits are summarised and injected into the LLM prompt for future iterations. The agent sees what the doctor consistently fixed and adjusts output accordingly |
| Improvement measurement | Edit distance tracked across 5 iterations. Before/after shown with metric cards and bar chart in the Learning tab |

### Why Correction Memory, Not Fine-Tuning?

Fine-tuning requires GPU, large datasets, and training time — not feasible in 48 hours with one patient. Correction memory is implementable, measurable, and explainable: the prompt grows richer with each iteration as the agent learns what the doctor consistently fixes. It also preserves the no-fabrication guardrail — fine-tuning can erode prompt-level safety rules.

### Results on Patient 2

| Metric | Baseline | After 3 iterations | Improvement |
|--------|----------|--------------------|-------------|
| Edit burden (edits made) | 4–5 | 1–2 | ~60% reduction |
| Edit distance | 35–45 | 10–18 | ~62% reduction |
| Missing field flags | 6 | 2 | ~67% reduction |

### Limitations of the Learning Loop

**Cold start.** With only one patient, the correction memory is thin. Across many patients the signal would be much stronger.

**Gaming risk.** An agent could reduce edit distance by becoming vaguer — writing less means less to edit. This is mitigated by the no-fabrication guardrail: sections cannot be removed, they must appear as sourced content or explicit MISSING. Vagueness is caught by post-processing verification.

**Simulated edits are not real clinician feedback.** The reviewer applies a fixed policy, not the nuanced judgment of an actual clinician. In production, real EHR audit trails would replace the simulation. The current implementation demonstrates the mechanism and proves the learning loop works.

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
| Part 2 edit burden reduction | ~60% |

**Discharge medications (8):** RACIPER 40mg, EMESET 4mg, OFLOX TZ, M STRONG, ZEDOTT, ENTRO, MEFTAL SPAS, LOPIRAMIDE 2mg

**Medication reconciliation:** Admission medications not clearly documented. Agent flagged `reconciliation_required: true` — did not infer from context.

**Drug interaction check:** No interactions detected against mock database.

---

## Limitations

**OCR accuracy on handwritten notes.** Tesseract degrades on low-quality handwriting. Several nursing notes pages produced partial or garbled text — flagged as conflicts rather than silently dropped.

**Single patient tested.** Regex patterns may miss non-standard medication formats in other patient files.

**Mock drug interaction database.** Hardcoded known pairs only — will miss interactions not in the mock set.

**LLM hallucination risk.** Guardrails reduce but cannot eliminate. Output always requires clinician sign-off.

**OCR speed.** 2–3 minutes for 71 pages — not real-time suitable without caching.

**No EMR integration.** Flags written to local JSON only.

**Simulated doctor edits.** Part 2 demonstrates the mechanism. Not a substitute for real clinician feedback data.

---

## What I Would Do With More Time

1. **Real clinician feedback loop** — Connect to EHR audit trails to replace simulated reviewer with actual doctor edits.
2. **Confidence scoring per section** — Assign confidence based on cross-note agreement, not just binary MISSING/present.
3. **Real drug interaction API** — OpenFDA or DrugBank integration.
4. **Multi-patient batch processing** — Run across all patients with aggregate reporting.
5. **Imaging follow-up tracking** — Patient_2's radiologist recommended contrast CT; build structured tracking so pending imaging is actively monitored.
6. **Preference fine-tuning (DPO)** — With enough (draft, edited) pairs, stronger improvement than prompt injection.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| PDF extraction | pdfplumber |
| OCR | Tesseract + poppler + pdf2image |
| LLM (primary) | Groq — Llama 3.1 8B Instant |
| LLM (fallback) | Google Gemini 2.0 Flash |
| Web interface | Streamlit |
| Visualisations | Plotly |
| Language | Python 3.13 |

---

## Project Structure

```
dscribe-agent/
├── app.py              # Streamlit web app
├── main.py             # CLI runner
├── reviewer.py         # Part 2 — simulated doctor reviewer
├── part2.py            # Part 2 — learning loop and metrics
├── requirements.txt
├── .env                # API keys (not committed)
├── README.md
├── data/               # Patient PDFs
├── outputs/            # Generated summaries and learning metrics
├── traces/             # Agent step traces (JSON)
└── screenshots/        # UI screenshots
```

---

## Assignment Requirements

| Requirement | Status |
|-------------|--------|
| Real agent loop | ✅ |
| PDF ingestion with OCR | ✅ |
| No fabrication guardrail (3 layers) | ✅ |
| Handle pending / missing data | ✅ |
| Medication reconciliation | ✅ |
| Handle conflicting information | ✅ |
| Mock external tools | ✅ |
| Tool retry / failure handling | ✅ |
| Hard iteration cap | ✅ |
| Step traces / observability | ✅ |
| Part 2 — simulated reviewer | ✅ |
| Part 2 — reward signal | ✅ |
| Part 2 — learning mechanism | ✅ |
| Part 2 — before/after metric | ✅ |
| Part 2 — limitations discussed | ✅ |

---

> ⚠️ **Disclaimer:** All output is AI-generated draft only. No clinical facts are invented. Clinician review required before any clinical use. All patient data is synthetic. Part 2 uses simulated doctor edits for demonstration purposes only.

*Built by Rinku Ghosh · AI Engineer · 2026*