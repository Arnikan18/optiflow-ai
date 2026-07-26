import os
from typing import Dict, Any

# =====================================================================
# OBJECTIVE PROFILE COEFFICIENTS (CONFIGURABLE)
# =====================================================================
# These profiles define coefficients for the weighted objective:
# Maximize: ARR_coeff * ARR + SLA_coeff * SLA + Skills_coeff * Skills - Unassigned_Penalty - Fairness_coeff * Max_Workload
#
# Skill Match Score Calculation:
# - For an incident 'i' and specialist 'j':
#   matched_skills = set(incident_required_skills) & set(specialist_skills)
#   score = len(matched_skills)
# - This yields 1 point per matching skill. The overall weight is governed
#   by the "skills" coefficient in the selected profile.
# =====================================================================

DEFAULT_PROFILES: Dict[str, Dict[str, int]] = {
    "Balanced": {
        "arr": 1,
        "sla": 1,
        "skills": 5,
        "fairness": 20,
        "unassigned_penalty": 10000
    },
    "SLA-First": {
        "arr": 5,
        "sla": 50,
        "skills": 2,
        "fairness": 1,
        "unassigned_penalty": 10000
    },
    "Revenue-First": {
        "arr": 100,
        "sla": 5,
        "skills": 2,
        "fairness": 1,
        "unassigned_penalty": 10000
    },
    "Fairness-First": {
        "arr": 1,
        "sla": 1,
        "skills": 2,
        "fairness": 100,
        "unassigned_penalty": 10000
    }
}

PROFILE_DESCRIPTIONS: Dict[str, str] = {
    "Balanced": "Distributes task workload evenly across specialists to prevent fatigue while ensuring skill matching.",
    "SLA-First": "Prioritizes urgent SLA deadlines and critical incidents first to minimize breach risk.",
    "Revenue-First": "Prioritizes escalations from high-ARR strategic customer accounts to protect commercial value.",
    "Fairness-First": "Strictly minimizes peak workloads to distribute support load equitably across specialists."
}

def get_profile_description(profile_name: str) -> str:
    """Retrieves human-readable description for the given profile."""
    return PROFILE_DESCRIPTIONS.get(profile_name.strip(), "")

def get_profile_weights(profile_name: str) -> Dict[str, int]:
    """Retrieves objective weights for the given profile name, falling back to Balanced if unknown."""
    name = profile_name.strip()
    profile = DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["Balanced"])
    
    # Optional environment overrides for dynamic configuration
    override_prefix = f"OPTIMIZER_WEIGHTS_{name.upper().replace('-', '_')}_"
    final_weights = {}
    for key, def_val in profile.items():
        env_key = f"{override_prefix}{key.upper()}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            try:
                final_weights[key] = int(env_val)
            except ValueError:
                final_weights[key] = def_val
        else:
            final_weights[key] = def_val
            
    return final_weights
