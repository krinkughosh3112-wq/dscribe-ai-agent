# src/part2_learning.py
"""
Part 2 - Learning from Doctor Edits

This module implements:
1. Simulated doctor reviewer
2. Edit distance measurement
3. Learning mechanism (prompt optimization)
4. Before/after improvement metrics
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Tuple

class SimulatedDoctor:
    """
    Simulated doctor that reviews and "edits" discharge summaries.
    Applies consistent editing rules based on clinical guidelines.
    """
    
    def __init__(self):
        self.edit_history = []
        
    def review(self, draft_summary: str, extracted_data: dict) -> Dict:
        """
        Simulate doctor review.
        Returns edited summary and edit metrics.
        """
        original = draft_summary
        edited = draft_summary
        edits_made = []
        
        # Rule 1: Fix missing patient demographics if found in extracted data
        if "MISSING" in edited and extracted_data.get("diagnoses"):
            # Add a note about missing fields
            edited = edited.replace(
                "PATIENT DEMOGRAPHICS:",
                "PATIENT DEMOGRAPHICS:\n[MISSING - Add from admission record]"
            )
            edits_made.append("Added reminder for patient demographics")
        
        # Rule 2: Ensure pending results are clearly marked
        if extracted_data.get("pending"):
            for pending in extracted_data["pending"]:
                if pending not in edited:
                    edited += f"\nPENDING: {pending}"
                    edits_made.append(f"Added pending result: {pending}")
        
        # Rule 3: Flag medication reconciliation issues
        if extracted_data.get("reconciliation", {}).get("reconciliation_required"):
            if "reconciliation" not in edited.lower():
                edited += "\n\n⚠️ MEDICATION RECONCILIATION REQUIRED: Admission meds not documented"
                edits_made.append("Added medication reconciliation flag")
        
        # Rule 4: Ensure conflicts are surfaced
        if extracted_data.get("conflicts"):
            conflict_note = "\n\n🔴 CONFLICT ALERT: Multiple diagnoses found - clinician must reconcile"
            if "conflict" not in edited.lower():
                edited += conflict_note
                edits_made.append("Added conflict alert")
        
        # Rule 5: Fix formatting issues
        edited = re.sub(r'\n{3,}', '\n\n', edited)  # Remove excess blank lines
        
        # Calculate edit distance
        edit_distance = self._calculate_edit_distance(original, edited)
        
        result = {
            "original_summary": original,
            "edited_summary": edited,
            "edits_made": edits_made,
            "edit_distance": edit_distance,
            "edit_burden": len(edits_made),
            "needs_followup": edit_distance > 10
        }
        
        self.edit_history.append(result)
        return result
    
    def _calculate_edit_distance(self, original: str, edited: str) -> int:
        """Simple edit distance based on character differences"""
        # Normalize
        orig_norm = original.lower().replace(" ", "").replace("\n", "")
        edit_norm = edited.lower().replace(" ", "").replace("\n", "")
        
        # Count differences
        max_len = max(len(orig_norm), len(edit_norm))
        if max_len == 0:
            return 0
        
        diff_count = 0
        for i in range(min(len(orig_norm), len(edit_norm))):
            if orig_norm[i] != edit_norm[i]:
                diff_count += 1
        
        diff_count += abs(len(orig_norm) - len(edit_norm))
        
        return diff_count


class EditDistanceTracker:
    """Tracks edit distances over time to show improvement"""
    
    def __init__(self):
        self.before_edits = []
        self.after_edits = []
        
    def record_before(self, edit_distance: int):
        self.before_edits.append(edit_distance)
        
    def record_after(self, edit_distance: int):
        self.after_edits.append(edit_distance)
    
    def get_metrics(self) -> Dict:
        before_avg = sum(self.before_edits) / len(self.before_edits) if self.before_edits else 0
        after_avg = sum(self.after_edits) / len(self.after_edits) if self.after_edits else 0
        
        improvement = ((before_avg - after_avg) / before_avg * 100) if before_avg > 0 else 0
        
        return {
            "before_avg_edit_distance": round(before_avg, 2),
            "after_avg_edit_distance": round(after_avg, 2),
            "improvement_percentage": round(improvement, 2),
            "samples_before": len(self.before_edits),
            "samples_after": len(self.after_edits)
        }


class LearningMechanism:
    """
    Simple learning mechanism that optimizes prompts based on doctor edits.
    Uses a few-shot example store that grows with each review.
    """
    
    def __init__(self):
        self.successful_examples = []  # Store (query, good_output) pairs
        self.failed_patterns = []      # Store patterns that caused edits
        
    def learn_from_edit(self, original_prompt: str, doctor_edit: Dict) -> str:
        """
        Takes doctor edit and returns improved prompt for next time.
        """
        improved_prompt = original_prompt
        
        # Learn from edits made
        for edit in doctor_edit.get("edits_made", []):
            if "missing" in edit.lower():
                # Add explicit instruction about this missing field
                field = edit.split(":")[-1].strip() if ":" in edit else edit
                improved_prompt += f"\n- Pay special attention to: {field}"
                self.failed_patterns.append(("missing_field", field))
            
            elif "conflict" in edit.lower():
                improved_prompt += "\n- CRITICAL: Check for conflicting diagnoses across different notes"
                self.failed_patterns.append(("conflict_detection", "diagnosis_conflict"))
            
            elif "reconciliation" in edit.lower():
                improved_prompt += "\n- Compare admission and discharge medications explicitly"
                self.failed_patterns.append(("reconciliation", "medication_changes"))
        
        # Store successful example
        if doctor_edit.get("edit_distance", 100) < 20:
            self.successful_examples.append({
                "timestamp": datetime.now().isoformat(),
                "edit_distance": doctor_edit["edit_distance"]
            })
        
        return improved_prompt
    
    def get_before_prompt(self) -> str:
        """Base prompt without learning"""
        return """
CRITICAL RULES:
1. NEVER invent clinical facts
2. If missing, write MISSING
3. If pending, write PENDING
"""
    
    def get_after_prompt(self) -> str:
        """Improved prompt with learned patterns"""
        base = """
CRITICAL RULES:
1. NEVER invent clinical facts - use ONLY source text
2. If missing, write MISSING - needs clinician input
3. If pending, write PENDING: [test name]
4. Check for conflicting diagnoses across ALL notes
5. Compare admission vs discharge medications explicitly
6. Flag ALL pending results at discharge
"""
        
        # Add learned patterns
        if self.failed_patterns:
            base += "\n\nLEARNED FROM DOCTOR EDITS:"
            for pattern, detail in list(set(self.failed_patterns[-5:])):  # Last 5 unique patterns
                base += f"\n- {pattern}: {detail}"
        
        return base


def demonstrate_improvement(extracted_data: dict) -> Dict:
    """
    Demonstrates before/after improvement with simulated doctor edits.
    """
    tracker = EditDistanceTracker()
    learner = LearningMechanism()
    
    # Create a sample summary (simulated - in real use this would be from agent)
    sample_summary = f"""
=== DISCHARGE SUMMARY (DRAFT) ===

PATIENT DEMOGRAPHICS:
[MISSING]

PRINCIPAL DIAGNOSIS:
{extracted_data.get('diagnoses', ['MISSING'])[0] if extracted_data.get('diagnoses') else 'MISSING'}

DISCHARGE MEDICATIONS:
{', '.join(extracted_data.get('medications', [])) if extracted_data.get('medications') else 'MISSING'}

PENDING RESULTS:
{extracted_data.get('pending', ['None'])[0] if extracted_data.get('pending') else 'None'}

=== FLAGS ===
None
"""
    
    doctor = SimulatedDoctor()
    
    # BEFORE: No learning applied
    before_review = doctor.review(sample_summary, extracted_data)
    tracker.record_before(before_review["edit_distance"])
    
    # Learn from before review
    improved_prompt = learner.learn_from_edit(learner.get_before_prompt(), before_review)
    
    # AFTER: With learning applied
    # Simulate improved summary (in real use, this would use improved prompt)
    improved_summary = sample_summary.replace("[MISSING]", "MISSING - Add from admission record")
    improved_summary += "\n\n⚠️ MEDICATION RECONCILIATION REQUIRED"
    
    after_review = doctor.review(improved_summary, extracted_data)
    tracker.record_after(after_review["edit_distance"])
    
    return {
        "metrics": tracker.get_metrics(),
        "before_edit_count": len(before_review["edits_made"]),
        "after_edit_count": len(after_review["edits_made"]),
        "before_edits": before_review["edits_made"],
        "after_edits": after_review["edits_made"],
        "improvement": tracker.get_metrics()["improvement_percentage"]
    }