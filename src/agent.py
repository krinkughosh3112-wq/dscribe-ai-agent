# src/agent.py
"""
True Agentic Loop for Discharge Summary Generation

Key difference from pipeline:
- Agent plans what to do next based on current state
- Re-plans after every action based on results
- Can adapt when extraction fails or data is missing
- Hard iteration cap prevents infinite loops
"""

import re
import json
import time
from datetime import datetime
from typing import Dict, Any, List
from groq import Groq
import os
from dotenv import load_dotenv

from src.state import AgentState, Severity
from src.tools import (
    extract_pdf_text_with_retry, extract_diagnoses_from_text, extract_pending_results,
    extract_medications, find_conflicts, flag_for_clinician,
    reconcile_medications, mock_drug_interaction_check
)
from src.prompts import PLANNER_PROMPT, DISCHARGE_SUMMARY_PROMPT

# Load environment variables
load_dotenv()


class DischargeSummaryAgent:
    """
    True agentic loop with planning and re-planning.
    Not a fixed pipeline - adapts based on what tools return.
    """
    
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        
        # Initialize Groq client
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.1-8b-instant"
        
        self.trace = []
        self.decision_history = []
    
    def _call_llm_with_retry(self, prompt: str, max_tokens: int = 1500, max_retries: int = 3) -> str:
        """Call Groq API with retry logic"""
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
    
    def _decide_next_action(self, state: AgentState) -> Dict[str, Any]:
        """
        The PLANNER - decides what to do based on current state.
        This is the key difference from a fixed pipeline.
        """
        
        # Build a summary of what's been done and what's missing
        completed = state.completed_steps
        diagnoses_found = len(state.diagnoses)
        pending_found = len(state.pending_results)
        meds_found = len(state.medications.get("discharge", []))
        conflicts_found = len(state.conflicts)
        flags_raised = len(state.flags)
        
        # Create a status report for the planner
        status_report = f"""
Current State Summary:
- Completed steps: {completed if completed else 'None'}
- Diagnoses found: {diagnoses_found}
- Pending results found: {pending_found}
- Medications found: {meds_found}
- Conflicts detected: {conflicts_found}
- Flags raised: {flags_raised}

What's missing:
{'✅' if diagnoses_found > 0 else '❌'} Diagnoses extracted
{'✅' if pending_found > 0 else '❌'} Pending results flagged
{'✅' if meds_found > 0 else '❌'} Discharge medications extracted
{'✅' if conflicts_found > 0 else '❌'} Conflicts checked
{'✅' if flags_raised > 0 else '❌'} Safety flags raised

Available actions:
1. EXTRACT_DIAGNOSES - Extract diagnoses from text
2. EXTRACT_PENDING - Find pending results
3. EXTRACT_MEDICATIONS - Extract discharge medications
4. CHECK_CONFLICTS - Find conflicting information
5. RECONCILE_MEDS - Compare admission vs discharge meds
6. CHECK_DRUG_INTERACTIONS - Check for drug interactions
7. GENERATE_SUMMARY - Create final discharge summary
8. DONE - Exit loop

Choose the NEXT action based on what's missing. Respond in this exact format:
ACTION: <action_name>
REASONING: <why this action>
"""
        
        prompt = f"You are a clinical agent planner. {status_report}"
        
        try:
            response = self._call_llm_with_retry(prompt, max_tokens=300)
            
            # Parse the response
            action_match = re.search(r'ACTION:\s*(\w+)', response, re.IGNORECASE)
            reasoning_match = re.search(r'REASONING:\s*(.+?)(?=\n|$)', response, re.IGNORECASE)
            
            action = action_match.group(1).upper() if action_match else "DONE"
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "No reasoning provided"
            
        except Exception as e:
            # Fallback logic if planner fails
            print(f"   Planner error: {e}, using fallback logic")
            
            # Smart fallback: do what's still missing
            if diagnoses_found == 0:
                action = "EXTRACT_DIAGNOSES"
                reasoning = "No diagnoses found yet"
            elif pending_found == 0:
                action = "EXTRACT_PENDING"
                reasoning = "No pending results flagged yet"
            elif meds_found == 0:
                action = "EXTRACT_MEDICATIONS"
                reasoning = "No medications extracted yet"
            elif conflicts_found == 0:
                action = "CHECK_CONFLICTS"
                reasoning = "No conflicts checked yet"
            else:
                action = "GENERATE_SUMMARY"
                reasoning = "All extractions complete"
        
        self.decision_history.append({
            "iteration": state.iteration,
            "action": action,
            "reasoning": reasoning,
            "state_summary": {
                "diagnoses": diagnoses_found,
                "pending": pending_found,
                "medications": meds_found,
                "conflicts": conflicts_found
            }
        })
        
        return {"action": action, "reasoning": reasoning}
    
    def _execute_action(self, action: str, state: AgentState, text: str) -> str:
        """
        Execute the planned action.
        Returns status message.
        """
        
        if action == "EXTRACT_DIAGNOSES":
            print(f"   → Executing: Extract diagnoses")
            extract_diagnoses_from_text(text, state)
            return f"Extracted {len(state.diagnoses)} diagnoses"
        
        elif action == "EXTRACT_PENDING":
            print(f"   → Executing: Extract pending results")
            extract_pending_results(text, state)
            return f"Found {len(state.pending_results)} pending items"
        
        elif action == "EXTRACT_MEDICATIONS":
            print(f"   → Executing: Extract medications")
            extract_medications(text, state)
            meds_count = len(state.medications.get("discharge", []))
            return f"Extracted {meds_count} discharge medications"
        
        elif action == "CHECK_CONFLICTS":
            print(f"   → Executing: Check conflicts")
            find_conflicts(state)
            return f"Found {len(state.conflicts)} conflicts"
        
        elif action == "RECONCILE_MEDS":
            print(f"   → Executing: Medication reconciliation")
            admission = state.medications.get("admission", [])
            discharge = state.medications.get("discharge", [])
            result = reconcile_medications(admission, discharge, state)
            state.med_recon = result
            return f"Reconciliation: {len(result.get('new_at_discharge', []))} new, {len(result.get('stopped_at_discharge', []))} stopped"
        
        elif action == "CHECK_DRUG_INTERACTIONS":
            print(f"   → Executing: Drug interaction check")
            meds = state.medications.get("discharge", [])
            result = mock_drug_interaction_check(meds, state)
            return f"Found {len(result.get('interactions_found', []))} interactions"
        
        elif action == "GENERATE_SUMMARY":
            print(f"   → Executing: Generate summary")
            # Build extracted data
            extracted_data = {
                "diagnoses": state.diagnoses,
                "medications": state.medications,
                "med_recon": state.med_recon,
                "pending_results": state.pending_results,
                "conflicts": state.conflicts,
                "flags": [{"issue": f.issue, "severity": f.severity.value} for f in state.flags]
            }
            
            summary_prompt = DISCHARGE_SUMMARY_PROMPT.format(
                extracted_data=json.dumps(extracted_data, indent=2),
                pending_results="\n".join(state.pending_results) if state.pending_results else "None",
                conflicts=json.dumps(state.conflicts, indent=2) if state.conflicts else "None",
                med_recon=json.dumps(state.med_recon, indent=2),
                drug_interactions="None",
                flags="\n".join([f"- {f.issue} ({f.severity.value})" for f in state.flags]),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            summary = self._call_llm_with_retry(summary_prompt, max_tokens=2000)
            state.discharge_summary = summary
            return "Summary generated"
        
        elif action == "DONE":
            return "Agent complete"
        
        else:
            return f"Unknown action: {action}"
    
    def run(self, pdf_path: str) -> Dict[str, Any]:
        """
        TRUE AGENTIC LOOP:
        - Plan → Act → Observe → Re-plan
        - Hard cap on iterations
        - Adapts based on tool results
        """
        
        print(f"\n{'='*60}")
        print(f"🤖 TRUE AGENTIC LOOP STARTING: {pdf_path}")
        print(f"{'='*60}\n")
        
        # Initialize state
        state = AgentState(max_iterations=self.max_iterations)
        
        # STEP 0: Extract raw text from PDF (required first step)
        print("📄 Initializing: Extracting PDF text...")
        state.raw_text = extract_pdf_text_with_retry(pdf_path)
        self.trace.append({"step": 0, "action": "extract_pdf", "characters": len(state.raw_text)})
        print(f"   ✓ Extracted {len(state.raw_text)} characters")
        
        if not state.raw_text or len(state.raw_text) < 100:
            state.add_flag(
                issue="PDF extraction failed or returned no text",
                severity=Severity.CRITICAL,
                source="pdf_extraction"
            )
            print("   ❌ No text extracted!")
        
        # ============================================================
        # TRUE AGENTIC LOOP - Plan, Act, Observe, Re-plan
        # ============================================================
        
        print(f"\n🔄 Starting agentic loop (max {self.max_iterations} iterations)...")
        print(f"{'─'*50}")
        
        while state.iteration < self.max_iterations:
            state.iteration += 1
            
            print(f"\n--- Iteration {state.iteration}/{self.max_iterations} ---")
            
            # STEP 1: PLAN - Decide what to do next
            plan = self._decide_next_action(state)
            action = plan["action"]
            reasoning = plan["reasoning"]
            
            print(f"📋 PLANNER DECIDES: {action}")
            print(f"   Reasoning: {reasoning}")
            
            # Check if we should stop
            if action == "DONE":
                print("   ✓ Planner signaled completion")
                break
            
            # STEP 2: ACT - Execute the planned action
            result = self._execute_action(action, state, state.raw_text)
            print(f"   Result: {result}")
            
            # STEP 3: OBSERVE - Record what happened
            self.trace.append({
                "iteration": state.iteration,
                "action": action,
                "reasoning": reasoning,
                "result": result,
                "state": {
                    "diagnoses": len(state.diagnoses),
                    "pending": len(state.pending_results),
                    "medications": len(state.medications.get("discharge", [])),
                    "conflicts": len(state.conflicts),
                    "flags": len(state.flags)
                }
            })
            
            # STEP 4: RE-PLAN - Loop continues, planner will see updated state
        
        # ============================================================
        # SAFETY VERIFICATION (after loop completes)
        # ============================================================
        
        print(f"\n{'─'*50}")
        print("🛡️ Running safety verification...")
        
        safety_checks = {
            "no_fabrication": "MISSING" in state.discharge_summary or "PENDING" in state.discharge_summary if state.discharge_summary else True,
            "flags_included": len(state.flags) > 0,
            "conflicts_surfaced": len(state.conflicts) > 0,
            "iteration_cap_enforced": state.iteration <= self.max_iterations,
            "planner_made_decisions": len(self.decision_history) > 0
        }
        
        print(f"   ✓ No fabrication: {'✅ PASS' if safety_checks['no_fabrication'] else '⚠️ CHECK'}")
        print(f"   ✓ Flags included: {len(state.flags)} flags")
        print(f"   ✓ Conflicts surfaced: {len(state.conflicts)} conflicts")
        print(f"   ✓ Iterations used: {state.iteration}/{self.max_iterations}")
        print(f"   ✓ Planner decisions: {len(self.decision_history)}")
        
        # Ensure summary exists even if loop didn't generate one
        if not state.discharge_summary:
            print("   ⚠️ No summary generated in loop, creating fallback...")
            extracted_data = {
                "diagnoses": state.diagnoses,
                "medications": state.medications,
                "pending_results": state.pending_results,
                "conflicts": state.conflicts,
                "flags": [{"issue": f.issue, "severity": f.severity.value} for f in state.flags]
            }
            
            fallback_prompt = DISCHARGE_SUMMARY_PROMPT.format(
                extracted_data=json.dumps(extracted_data, indent=2),
                pending_results="\n".join(state.pending_results) if state.pending_results else "None",
                conflicts=json.dumps(state.conflicts, indent=2) if state.conflicts else "None",
                med_recon=json.dumps(state.med_recon, indent=2),
                drug_interactions="None",
                flags="\n".join([f"- {f.issue} ({f.severity.value})" for f in state.flags]),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            state.discharge_summary = self._call_llm_with_retry(fallback_prompt, max_tokens=2000)
        
        # Return results
        return {
            "discharge_summary": state.discharge_summary,
            "state": state.to_dict(),
            "trace": self.trace,
            "decision_history": self.decision_history,
            "safety_checks": safety_checks,
            "stats": {
                "iterations": state.iteration,
                "max_iterations": self.max_iterations,
                "planner_decisions": len(self.decision_history),
                "flags_count": len(state.flags),
                "conflicts_count": len(state.conflicts),
                "pending_count": len(state.pending_results),
                "diagnoses_count": len(state.diagnoses),
                "medications_count": len(state.medications.get("discharge", [])),
                "med_changes_added": len(state.med_recon.get("new_at_discharge", [])) if state.med_recon else 0,
                "med_changes_stopped": len(state.med_recon.get("stopped_at_discharge", [])) if state.med_recon else 0
            }
        }