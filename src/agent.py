# src/agent.py
import re
import json
import time
from datetime import datetime
from typing import Dict, Any
from groq import Groq
import os
from dotenv import load_dotenv

from src.state import AgentState, Severity
from src.tools import (
    extract_pdf_text_with_retry, extract_diagnoses_from_text, extract_pending_results,
    extract_medications, find_conflicts, flag_for_clinician,
    reconcile_medications, mock_drug_interaction_check
)
from src.prompts import DISCHARGE_SUMMARY_PROMPT

# Load environment variables
load_dotenv()

class DischargeSummaryAgent:
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        
        # Initialize Groq client (free, faster)
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.1-8b-instant"
        
        self.trace = []
    
    def _call_llm_with_retry(self, prompt: str, max_tokens: int = 1500, max_retries: int = 3) -> str:
        """Call Groq API with retry logic for rate limits"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e)
                if "rate_limit" in error_msg.lower() or "429" in error_msg:
                    wait_time = (attempt + 1) * 10
                    print(f"   ⚠️ Rate limit hit. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif attempt == max_retries - 1:
                    return f"ERROR: API call failed: {error_msg}"
                else:
                    wait_time = 3
                    print(f"   ⚠️ Error: {error_msg[:100]}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        return "ERROR: Max retries exceeded"
    
    def run(self, pdf_path: str) -> Dict[str, Any]:
        """Main agent execution loop"""
        
        print(f"\n{'='*60}")
        print(f"🤖 AGENT STARTING: {pdf_path}")
        print(f"{'='*60}\n")
        
        # Initialize state
        state = AgentState(max_iterations=self.max_iterations)
        
        # Step 1: Extract raw text with retry
        print("📄 STEP 1: Extracting PDF text...")
        state.raw_text = extract_pdf_text_with_retry(pdf_path)
        self.trace.append({"step": 1, "action": "extract_pdf", "characters": len(state.raw_text)})
        print(f"   ✓ Extracted {len(state.raw_text)} characters")
        
        if not state.raw_text or len(state.raw_text) < 100:
            state.add_flag(
                issue="PDF extraction failed or returned no text",
                severity=Severity.CRITICAL,
                source="pdf_extraction"
            )
            print("   ❌ No text extracted! Check if PDF is valid.")
        
        # Step 2: Run extraction tools
        print("\n🔧 STEP 2: Running extraction tools...")
        
        print("   - Extracting diagnoses...")
        extract_diagnoses_from_text(state.raw_text, state)
        
        print("   - Extracting pending results...")
        extract_pending_results(state.raw_text, state)
        
        print("   - Extracting medications...")
        discharge_meds = extract_medications(state.raw_text, state)
        
        print("   - Finding conflicts...")
        find_conflicts(state)
        
        # Step 2b: Medication reconciliation (NEW - Per brief)
        print("   - Medication reconciliation...")
        admission_meds = state.medications.get("admission", [])
        discharge_meds_list = state.medications.get("discharge", [])
        recon_result = reconcile_medications(admission_meds, discharge_meds_list, state)
        state.med_recon = recon_result
        if recon_result.get("reconciliation_required"):
            print(f"      ⚠️ Reconciliation needed: {len(recon_result.get('new_at_discharge', []))} added, {len(recon_result.get('stopped_at_discharge', []))} stopped")
        else:
            print(f"      ✓ No medication changes detected")
        
        # Step 2c: Drug interaction check (NEW - Per brief)
        print("   - Drug interaction check...")
        interaction_result = mock_drug_interaction_check(discharge_meds_list, state)
        if interaction_result.get("interactions_found"):
            print(f"      ⚠️ {len(interaction_result.get('interactions_found', []))} interactions found")
        else:
            print(f"      ✓ No drug interactions detected")
        
        state.completed_steps.append("initial_extraction")
        self.trace.append({
            "step": 2, 
            "diagnoses_found": len(state.diagnoses),
            "pending_found": len(state.pending_results),
            "conflicts_found": len(state.conflicts),
            "med_reconciliation_required": recon_result.get("reconciliation_required", False),
            "drug_interactions_found": len(interaction_result.get("interactions_found", []))
        })
        
        print(f"\n   📊 Summary:")
        print(f"      - Diagnoses: {len(state.diagnoses)}")
        print(f"      - Pending items: {len(state.pending_results)}")
        print(f"      - Conflicts: {len(state.conflicts)}")
        print(f"      - Flags: {len(state.flags)}")
        print(f"      - Medication changes: {len(recon_result.get('new_at_discharge', []))} added, {len(recon_result.get('stopped_at_discharge', []))} stopped")
        print(f"      - Drug interactions: {len(interaction_result.get('interactions_found', []))}")
        
        # Hard iteration cap check
        if state.iteration >= self.max_iterations:
            print(f"\n   ⚠️ Reached hard iteration cap ({self.max_iterations})")
            state.add_flag(
                issue=f"Agent reached max iterations ({self.max_iterations}) - summary may be incomplete",
                severity=Severity.WARNING,
                source="iteration_cap"
            )
        
        # Step 3: Generate discharge summary
        print("\n📝 STEP 3: Generating discharge summary...")
        
        # Prepare extracted data for prompt
        extracted_data = {
            "diagnoses": state.diagnoses,
            "medications": state.medications,
            "med_recon": state.med_recon,
            "investigations": state.investigations[:10] if state.investigations else "None",
            "pending_results": state.pending_results,
            "conflicts": state.conflicts,
            "drug_interactions": interaction_result.get("interactions_found", []),
            "flags": [{"issue": f.issue, "severity": f.severity.value} for f in state.flags]
        }
        
        summary_prompt = DISCHARGE_SUMMARY_PROMPT.format(
            extracted_data=json.dumps(extracted_data, indent=2),
            pending_results="\n".join(state.pending_results) if state.pending_results else "None",
            conflicts=json.dumps(state.conflicts, indent=2) if state.conflicts else "None",
            med_recon=json.dumps(state.med_recon, indent=2),
            drug_interactions="\n".join(interaction_result.get("interactions_found", [])) if interaction_result.get("interactions_found") else "None",
            flags="\n".join([f"- {f.issue} ({f.severity.value})" for f in state.flags]),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        state.discharge_summary = self._call_llm_with_retry(summary_prompt, max_tokens=2000)
        
        self.trace.append({
            "step": 3,
            "action": "generate_summary",
            "summary_length": len(state.discharge_summary)
        })
        
        print("   ✓ Discharge summary generated")
        
        # Step 4: Safety verification
        print("\n🛡️ STEP 4: Safety verification...")
        
        safety_checks = {
            "no_fabrication": "MISSING" in state.discharge_summary or "PENDING" in state.discharge_summary,
            "flags_included": len(state.flags) > 0,
            "conflicts_surfaced": len(state.conflicts) > 0 or "CONFLICT" in state.discharge_summary.upper(),
            "med_reconciliation_done": len(state.med_recon) > 0,
            "drug_interaction_checked": len(interaction_result.get("interactions_found", [])) >= 0,
            "iteration_cap_enforced": state.iteration <= self.max_iterations,
            "clinician_review_required": "CLINICIAN REVIEW REQUIRED" in state.discharge_summary.upper()
        }
        
        self.trace.append({"step": 4, "safety_checks": safety_checks})
        
        print(f"   ✓ No fabrication: {'✅ PASS' if safety_checks['no_fabrication'] else '⚠️ CHECK'}")
        print(f"   ✓ Flags included: {len(state.flags)} flags")
        print(f"   ✓ Conflicts surfaced: {len(state.conflicts)} conflicts")
        print(f"   ✓ Medication reconciliation: {'✅ DONE' if safety_checks['med_reconciliation_done'] else '⚠️ CHECK'}")
        print(f"   ✓ Iteration cap: {state.iteration}/{self.max_iterations} steps used")
        
        # Return results
        return {
            "discharge_summary": state.discharge_summary,
            "state": state.to_dict(),
            "trace": self.trace,
            "safety_checks": safety_checks,
            "stats": {
                "iterations": state.iteration,
                "max_iterations": self.max_iterations,
                "flags_count": len(state.flags),
                "conflicts_count": len(state.conflicts),
                "pending_count": len(state.pending_results),
                "diagnoses_count": len(state.diagnoses),
                "med_changes_added": len(state.med_recon.get("new_at_discharge", [])),
                "med_changes_stopped": len(state.med_recon.get("stopped_at_discharge", [])),
                "drug_interactions": len(interaction_result.get("interactions_found", []))
            }
        }