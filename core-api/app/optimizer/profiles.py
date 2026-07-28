import os
from typing import Any, Dict


PROFILE_ORDER: tuple[str, ...] = (
    "BALANCED",
    "SLA_FIRST",
    "REVENUE_FIRST",
    "FAIRNESS_FIRST",
)

PROFILE_ALIASES = {
    "BALANCED": "BALANCED",
    "SLA-FIRST": "SLA_FIRST",
    "SLA_FIRST": "SLA_FIRST",
    "REVENUE-FIRST": "REVENUE_FIRST",
    "REVENUE_FIRST": "REVENUE_FIRST",
    "FAIRNESS-FIRST": "FAIRNESS_FIRST",
    "FAIRNESS_FIRST": "FAIRNESS_FIRST",
}

DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "BALANCED": {
        "profile_id": "BALANCED",
        "profile_name": "Balanced",
        "description": (
            "Balances SLA protection, revenue protection, fairness, workload stability, "
            "and context-switching control."
        ),
        "weights": {
            "arr": 8,
            "sla": 8,
            "skills": 10,
            "fairness": 8,
            "context_switch": 6,
            "unassigned_penalty": 10000,
        },
    },
    "SLA_FIRST": {
        "profile_id": "SLA_FIRST",
        "profile_name": "SLA First",
        "description": "Prioritizes avoiding SLA breaches while keeping revenue and fairness in the objective.",
        "weights": {
            "arr": 5,
            "sla": 40,
            "skills": 8,
            "fairness": 5,
            "context_switch": 4,
            "unassigned_penalty": 10000,
        },
    },
    "REVENUE_FIRST": {
        "profile_id": "REVENUE_FIRST",
        "profile_name": "Revenue First",
        "description": "Prioritizes ARR and strategic customer protection while still considering SLA and fairness.",
        "weights": {
            "arr": 45,
            "sla": 8,
            "skills": 8,
            "fairness": 5,
            "context_switch": 4,
            "unassigned_penalty": 10000,
        },
    },
    "FAIRNESS_FIRST": {
        "profile_id": "FAIRNESS_FIRST",
        "profile_name": "Fairness First",
        "description": "Prioritizes balanced specialist workload and avoids overloading individual specialists.",
        "weights": {
            "arr": 5,
            "sla": 8,
            "skills": 8,
            "fairness": 45,
            "context_switch": 12,
            "unassigned_penalty": 10000,
        },
    },
}


def normalize_profile_id(profile_name: str) -> str:
    normalized = profile_name.strip().upper().replace(" ", "_")
    return PROFILE_ALIASES.get(normalized, PROFILE_ALIASES.get(normalized.replace("_", "-"), "BALANCED"))


def get_profile_definition(profile_name: str) -> Dict[str, Any]:
    return DEFAULT_PROFILES[normalize_profile_id(profile_name)]


def get_profile_description(profile_name: str) -> str:
    return str(get_profile_definition(profile_name)["description"])


def get_profile_display_name(profile_name: str) -> str:
    return str(get_profile_definition(profile_name)["profile_name"])


def get_profile_weights(profile_name: str) -> Dict[str, int]:
    profile = get_profile_definition(profile_name)
    profile_id = str(profile["profile_id"])
    defaults = dict(profile["weights"])

    override_prefix = f"OPTIMIZER_WEIGHTS_{profile_id}_"
    final_weights: dict[str, int] = {}
    for key, default_value in defaults.items():
        env_value = os.getenv(f"{override_prefix}{key.upper()}")
        if env_value is None:
            final_weights[key] = int(default_value)
            continue
        try:
            final_weights[key] = int(env_value)
        except ValueError:
            final_weights[key] = int(default_value)
    return final_weights
