# src/tools.py
import pdfplumber
import re
import time
from typing import List, Dict, Tuple
from src.state import AgentState, Severity
import os

# Try to import OCR libraries
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
    
    # Set Tesseract path for Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # Set poppler path
    POPPLER_PATH = r'C:\Users\Smart\Desktop\shop o\Release-23.11.0-0\poppler-23.11.0\Library\bin'
    
    if os.path.exists(POPPLER_PATH):
        print(f"✓ Poppler found at: {POPPLER_PATH}")
    else:
        print(f"⚠️ Poppler not found at {POPPLER_PATH}")
        
except ImportError as e:
    OCR_AVAILABLE = False
    print(f"⚠️ OCR libraries not available: {e}")

# ============================================================
# 1. PDF EXTRACTION WITH RETRY
# ============================================================

def extract_pdf_text_with_retry(pdf_path: str, max_retries: int = 2) -> str:
    """Extract PDF text with retry logic for failures"""
    for attempt in range(max_retries):
        try:
            result = extract_pdf_text(pdf_path)
            if result and len(result) > 100:
                return result
            if attempt < max_retries - 1:
                print(f"   Retry {attempt + 1}/{max_retries}...")
                time.sleep(2)
        except Exception as e:
            print(f"   Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                return ""
            time.sleep(2)
    return ""

def extract_pdf_text(pdf_path: str) -> str:
    """Extract and clean text from PDF - supports both text and scanned PDFs"""
    full_text = ""
    
    # Method 1: Try pdfplumber first (for text-based PDFs)
    print("   Method 1: Trying pdfplumber...")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                
                # Skip garbage pages (mostly repeated numbers)
                lines = text.split('\n')
                number_lines = sum(1 for line in lines if re.match(r'^[\d\s]+$', line.strip()))
                total_lines = len([l for l in lines if l.strip()])
                
                if total_lines > 0 and (number_lines / total_lines) > 0.7:
                    continue
                    
                if len(text.strip()) < 100:
                    continue
                    
                full_text += f"\n--- PAGE {page_num + 1} ---\n{text}\n"
        
        if full_text:
            print(f"   ✓ Extracted {len(full_text)} characters using pdfplumber")
            return full_text
        else:
            print("   No text found with pdfplumber, trying OCR...")
    except Exception as e:
        print(f"   pdfplumber failed: {e}")
    
    # Method 2: Try OCR for scanned PDFs
    if OCR_AVAILABLE:
        print("\n   Method 2: Trying OCR for scanned PDF...")
        try:
            print("   Converting PDF to images (may take 2-3 minutes)...")
            images = convert_from_path(pdf_path, dpi=200, poppler_path=POPPLER_PATH)
            print(f"   ✓ Converted {len(images)} pages")
            
            print("   Running OCR on each page...")
            for page_num, image in enumerate(images):
                if page_num % 10 == 0:
                    print(f"   Processing page {page_num + 1}/{len(images)}...")
                
                text = pytesseract.image_to_string(image)
                
                # Clean the text
                lines = text.split('\n')
                cleaned_lines = []
                for line in lines:
                    if re.match(r'^[\d\s]+$', line.strip()):
                        continue
                    if len(line.strip()) > 2:
                        cleaned_lines.append(line)
                
                cleaned_text = '\n'.join(cleaned_lines)
                
                if len(cleaned_text.strip()) > 50:
                    full_text += f"\n--- PAGE {page_num + 1} ---\n{cleaned_text}\n"
            
            if full_text:
                print(f"   ✓ Extracted {len(full_text)} characters using OCR")
                return full_text
            else:
                print("   ❌ OCR found no text on any page")
                
        except Exception as e:
            print(f"   ❌ OCR failed: {e}")
    else:
        print("   ❌ OCR not available")
    
    if not full_text:
        print("\n   ❌ ERROR: Could not extract any text from PDF!")
    
    return full_text

# ============================================================
# 2. DIAGNOSIS EXTRACTION
# ============================================================

def extract_diagnoses_from_text(text: str, state: AgentState) -> None:
    """Extract all diagnoses found across different sections"""
    
    patterns = [
        (r'DIAGNOSIS\s*:?\s*(.*?)(?=\n\s*[A-Z]+:|$)', "diagnosis_section"),
        (r'FINAL DIAGNOSIS\s*:?\s*(.*?)(?=\n\s*[A-Z]+:|$)', "final_diagnosis"),
        (r'IMPRESSION\s*:?\s*(.*?)(?=\n\s*[A-Z]+:|$)', "impression"),
        (r'DISCHARGE DIAGNOSIS\s*:?\s*(.*?)(?=\n\s*[A-Z]+:|$)', "discharge_diagnosis"),
    ]
    
    for pattern, source in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            clean = match.strip().replace('\n', ' ')
            if clean and len(clean) > 5 and len(clean) < 500:
                state.add_diagnosis(clean[:200], source)
                print(f"   ✓ Found diagnosis: {clean[:80]}...")

# ============================================================
# 3. PENDING RESULTS DETECTION
# ============================================================

def extract_pending_results(text: str, state: AgentState) -> None:
    """Extract pending/awaited results"""
    patterns = [
        r'(?i)([^.]*?(?:report|result|culture|sensitivity)[^.]*?(?:awaited|pending|sent|not yet)[^.]*?)\.',
        r'(?i)([^.]*?not[^.]*?(?:received|available|back)[^.]*?)\.',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            clean = match.strip()
            if clean and len(clean) > 10 and len(clean) < 200:
                if clean not in state.pending_results:
                    state.pending_results.append(clean)
                    state.add_flag(
                        issue=f"Pending: {clean[:100]}",
                        severity=Severity.WARNING,
                        source="pending_detection"
                    )
                    print(f"   ⚠ Pending: {clean[:80]}...")

# ============================================================
# 4. MEDICATION EXTRACTION
# ============================================================

def extract_medications(text: str, state: AgentState) -> List[Dict]:
    """Extract medications from drug charts and discharge advice"""
    
    discharge_meds = []
    
    # Look for discharge medication table
    table_pattern = r'TAB\.?\s+([A-Z\s]+?)\s+(\d+(?:mg|gm|mcg)?)\s+([\d-]+(?:-[-\d]+)?)\s+(\d+\s+DAYS?)'
    matches = re.findall(table_pattern, text, re.IGNORECASE)
    
    for match in matches:
        discharge_meds.append({
            "name": match[0].strip(),
            "dosage": match[1],
            "frequency": match[2],
            "duration": match[3]
        })
    
    # Also look for simple medication names
    simple_pattern = r'TAB\.?\s+([A-Z\s]+?)\s+(\d+(?:mg|gm|mcg)?)'
    simple_matches = re.findall(simple_pattern, text, re.IGNORECASE)
    
    for match in simple_matches:
        med_name = match[0].strip()
        med_dose = match[1]
        if not any(m["name"] == med_name for m in discharge_meds):
            discharge_meds.append({"name": med_name, "dosage": med_dose, "frequency": "", "duration": ""})
    
    if discharge_meds:
        state.medications["discharge"] = discharge_meds
        print(f"   ✓ Found {len(discharge_meds)} discharge medications")
    
    # Look for admission medications
    admission_pattern = r'ADMISSION MEDICATIONS?:?\s*(.*?)(?=\n\s*[A-Z]+:|$)'
    adm_match = re.search(admission_pattern, text, re.IGNORECASE | re.DOTALL)
    if adm_match:
        adm_text = adm_match.group(1).strip()
        if adm_text:
            # Simple extraction of admission meds
            adm_meds = []
            adm_simple = re.findall(r'([A-Z][A-Z\s]+?)\s+(\d+(?:mg|gm|mcg)?)', adm_text, re.IGNORECASE)
            for match in adm_simple:
                adm_meds.append({"name": match[0].strip(), "dosage": match[1]})
            if adm_meds:
                state.medications["admission"] = adm_meds
                print(f"   ✓ Found {len(adm_meds)} admission medications")
    
    return discharge_meds

# ============================================================
# 5. MEDICATION RECONCILIATION (Per Brief Requirement)
# ============================================================

def reconcile_medications(admission_meds: list, discharge_meds: list, state: AgentState) -> dict:
    """
    Compare admission vs discharge medications, flag unexplained changes.
    This is explicitly required by the assignment brief.
    """
    
    # Normalize medication names
    def normalize_name(name: str) -> str:
        return name.lower().strip().replace("tab", "").replace(".", "").strip()
    
    adm_set = set()
    for m in admission_meds:
        name = m.get("name", "")
        if name:
            adm_set.add(normalize_name(name))
    
    dis_set = set()
    for m in discharge_meds:
        name = m.get("name", "")
        if name:
            dis_set.add(normalize_name(name))
    
    # Find changes
    new_meds = dis_set - adm_set
    stopped_meds = adm_set - dis_set
    continued_meds = adm_set & dis_set
    
    # Flag any undocumented changes
    if new_meds or stopped_meds:
        state.add_flag(
            issue=f"Medication changes without documented reason. Added: {list(new_meds)[:5]}, Stopped: {list(stopped_meds)[:5]}",
            severity=Severity.WARNING,
            source="medication_reconciliation"
        )
        print(f"   🔄 Medication reconciliation: {len(new_meds)} added, {len(stopped_meds)} stopped")
    
    return {
        "new_at_discharge": list(new_meds),
        "stopped_at_discharge": list(stopped_meds),
        "continued_unchanged": list(continued_meds),
        "reconciliation_required": len(new_meds) + len(stopped_meds) > 0,
        "total_admission_meds": len(adm_set),
        "total_discharge_meds": len(dis_set)
    }

# ============================================================
# 6. DRUG INTERACTION CHECK (Mock Tool per Brief)
# ============================================================

def mock_drug_interaction_check(medications: list, state: AgentState) -> dict:
    """
    Mock drug interaction checker.
    Per assignment brief: "mock external tools and agent must decide when to call them"
    """
    
    if not medications:
        return {"status": "no_meds", "interactions_found": [], "safety_flags": []}
    
    # Common drug interaction pairs (simplified for mock)
    interaction_pairs = {
        ("warfarin", "aspirin"): "Increased bleeding risk - monitor INR closely",
        ("warfarin", "clopidogrel"): "Significant bleeding risk - consider GI protection",
        ("metformin", "contrast"): "Risk of lactic acidosis - hold metformin before procedure",
        ("lisinopril", "spironolactone"): "Risk of hyperkalemia - monitor potassium",
        ("amiodarone", "digoxin"): "Digoxin toxicity risk - reduce digoxin dose",
        ("ciprofloxacin", "theophylline"): "Theophylline toxicity - monitor levels",
        ("simvastatin", "clarithromycin"): "Statin toxicity risk - consider alternative",
        ("methotrexate", "trimethoprim"): "Severe bone marrow suppression - avoid combination",
    }
    
    # Get medication names
    med_names = []
    for m in medications:
        name = m.get("name", "") if isinstance(m, dict) else str(m)
        med_names.append(name.lower().strip())
    
    interactions_found = []
    safety_flags = []
    
    for (drug1, drug2), warning in interaction_pairs.items():
        drug1_present = any(drug1 in name for name in med_names)
        drug2_present = any(drug2 in name for name in med_names)
        
        if drug1_present and drug2_present:
            interaction_msg = f"{drug1} + {drug2}: {warning}"
            interactions_found.append(interaction_msg)
            safety_flags.append(f"⚠️ DRUG INTERACTION: {interaction_msg}")
            
            # Add to state flags
            state.add_flag(
                issue=f"Drug interaction detected: {drug1} + {drug2} - {warning}",
                severity=Severity.WARNING,
                source="drug_interaction_check"
            )
            print(f"   💊 Drug interaction found: {drug1} + {drug2}")
    
    return {
        "status": "success",
        "tool": "mock_drug_interaction_checker",
        "medications_checked": len(medications),
        "interactions_found": interactions_found,
        "safety_flags": safety_flags
    }

# ============================================================
# 7. CONFLICT DETECTION
# ============================================================

def find_conflicts(state: AgentState) -> None:
    """Find conflicting information across notes"""
    
    # Check for conflicting diagnoses
    diagnoses_list = [d["diagnosis"] for d in state.diagnoses]
    if len(set(diagnoses_list)) > 1:
        unique_dx = []
        for dx in diagnoses_list:
            short_dx = dx[:50]
            if short_dx not in [u[:50] for u in unique_dx]:
                unique_dx.append(dx)
        
        if len(unique_dx) > 1:
            state.add_conflict(
                field="diagnosis",
                values=unique_dx[:3],
                sources=[d["source"] for d in state.diagnoses][:3]
            )
            state.add_flag(
                issue=f"Conflicting diagnoses across notes: {unique_dx[0][:40]} vs {unique_dx[1][:40] if len(unique_dx) > 1 else 'other'}",
                severity=Severity.CRITICAL,
                source="conflict_detection"
            )
            print(f"   🔴 Conflict found in diagnoses")
    
    # Check for lab value conflicts
    hb_values = re.findall(r'Haemoglobin.*?(\d+\.?\d*)\s*gm/dL', state.raw_text, re.IGNORECASE)
    if len(set(hb_values)) > 1:
        state.add_flag(
            issue=f"Conflicting Haemoglobin values: {', '.join(hb_values)}",
            severity=Severity.WARNING,
            source="lab_conflict"
        )
        print(f"   🔴 Conflict found in lab values")

# ============================================================
# 8. CLINICIAN FLAG
# ============================================================

def flag_for_clinician(issue: str, severity: Severity, state: AgentState):
    """Add a flag for clinician review"""
    state.add_flag(issue, severity, "explicit_flag")
    print(f"   🚩 Flag added: {issue[:80]}...")