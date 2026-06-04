# src/state.py
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime

class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Flag:
    """A flag for clinician review"""
    issue: str
    severity: Severity
    source: str  # Which document/page
    details: str = ""

@dataclass
class AgentState:
    """State maintained throughout agent execution"""
    # Raw data
    raw_text: str = ""
    extracted_sections: Dict[str, str] = field(default_factory=dict)
    
    # Findings
    diagnoses: List[Dict] = field(default_factory=list)  # diagnosis + source
    medications: Dict[str, List] = field(default_factory=dict)  # admission vs discharge
    investigations: List[Dict] = field(default_factory=list)
    pending_results: List[str] = field(default_factory=list)
    
    # Safety
    flags: List[Flag] = field(default_factory=list)
    conflicts: List[Dict] = field(default_factory=list)
    
    # Medication reconciliation (NEW - Per brief requirement)
    med_recon: Dict = field(default_factory=dict)
    
    # Execution
    plan: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 10
    
    # Output
    discharge_summary: str = ""
    
    def add_flag(self, issue: str, severity: Severity, source: str, details: str = ""):
        self.flags.append(Flag(issue, severity, source, details))
    
    def add_conflict(self, field: str, values: List[str], sources: List[str]):
        self.conflicts.append({
            "field": field,
            "values": values,
            "sources": sources,
            "resolved": False
        })
    
    def add_diagnosis(self, diagnosis: str, source: str):
        self.diagnoses.append({"diagnosis": diagnosis, "source": source})
    
    def to_dict(self) -> dict:
        return {
            "diagnoses": self.diagnoses,
            "medications": self.medications,
            "med_recon": self.med_recon,
            "investigations": self.investigations,
            "pending_results": self.pending_results,
            "flags": [{"issue": f.issue, "severity": f.severity.value, "source": f.source} for f in self.flags],
            "conflicts": self.conflicts,
            "completed_steps": self.completed_steps,
            "iterations": self.iteration,
            "discharge_summary": self.discharge_summary
        }