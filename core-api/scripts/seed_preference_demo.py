"""Seed deterministic manager preference history for the OptiFlow demo.

The script is intentionally opt-in. Without ``--apply`` it only prints the
planned seed. When applied, it backs up the current preference JSON, replaces
only previously generated ``RUN-PREF-DEMO-*`` audit rows, and writes a coherent
aggregate memory plus recent decision history.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete

from app.config.preference_config import OptimizationProfile, PreferenceConfig
from app.database.models import AgentRun, RunEvent
from app.database.persistence import save_agent_run, save_run_event
from app.database.session import async_session
from app.services.manager_preference_service import (
    ManagerPreferenceService,
    PreferenceMemory,
    RecommendationStats,
)


SEED_RUN_PREFIX = "RUN-PREF-DEMO-"
DEFAULT_DECISIONS = PreferenceConfig.MATURE_LEARNING_RUNS
DEFAULT_PREFERRED_COUNT = max(1, round(DEFAULT_DECISIONS * 0.8))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed preference memory for the demo")
    parser.add_argument(
        "--profile",
        choices=[profile.value for profile in OptimizationProfile],
        default=OptimizationProfile.SLA_FIRST.value,
        help="Profile that should become the learned preference",
    )
    parser.add_argument(
        "--decisions",
        type=int,
        default=DEFAULT_DECISIONS,
        help="Total approval decisions to seed (defaults to the mature threshold)",
    )
    parser.add_argument(
        "--preferred-count",
        type=int,
        default=DEFAULT_PREFERRED_COUNT,
        help="Decisions that select the preferred profile (defaults to 80%)",
    )
    parser.add_argument(
        "--backup-path",
        type=Path,
        default=Path("/tmp/optiflow-preference-memory-backup.json"),
        help="JSON file receiving the previous preference memory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually replace the demo preference seed",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.decisions < 1:
        raise ValueError("--decisions must be at least 1")
    if args.preferred_count < 0 or args.preferred_count > args.decisions:
        raise ValueError("--preferred-count must be between 0 and --decisions")


def alternative_profile(preferred: str) -> str:
    return (
        OptimizationProfile.BALANCED.value
        if preferred != OptimizationProfile.BALANCED.value
        else OptimizationProfile.SLA_FIRST.value
    )


async def seed(args: argparse.Namespace) -> None:
    preferred = PreferenceConfig.normalize_profile(args.profile).value
    alternate = alternative_profile(preferred)
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        async with session.begin():
            existing = await ManagerPreferenceService.load_memory(session)
            args.backup_path.parent.mkdir(parents=True, exist_ok=True)
            args.backup_path.write_text(
                existing.model_dump_json(indent=2),
                encoding="utf-8",
            )

            await session.execute(
                delete(RunEvent).where(RunEvent.run_id.like(f"{SEED_RUN_PREFIX}%"))
            )
            await session.execute(
                delete(AgentRun).where(AgentRun.run_id.like(f"{SEED_RUN_PREFIX}%"))
            )

            profile_counts = {
                profile.value: 0
                for profile in OptimizationProfile
            }
            profile_counts[preferred] = args.preferred_count
            profile_counts[alternate] = args.decisions - args.preferred_count
            memory = PreferenceMemory(
                total_runs=args.decisions,
                profile_counts=profile_counts,
                recommendation_statistics=RecommendationStats(
                    shown=args.decisions,
                    accepted=args.preferred_count,
                    rejected=args.decisions - args.preferred_count,
                    last_updated=now,
                    last_recommendation_timestamp=now,
                ),
                learned_constraints=[
                    "Protect renewals",
                    "Avoid specialist overload",
                ],
                updated_at=now,
            )
            saved = await ManagerPreferenceService.save_memory(session, memory)
            if not saved:
                raise RuntimeError("Preference memory seed could not be saved")

            alternate_count = args.decisions - args.preferred_count
            for index in range(args.decisions):
                run_id = f"{SEED_RUN_PREFIX}{index + 1:03d}"
                selected = alternate if index < alternate_count else preferred
                await save_agent_run(
                    session=session,
                    run_id=run_id,
                    scenario_id="preference_demo_seed",
                    status="COMPLETED",
                    goal_text="Protect urgent customers while respecting available capacity.",
                    current_node="complete_run",
                    completed_at=now,
                )
                await save_run_event(
                    session=session,
                    run_id=run_id,
                    sequence_number=1,
                    event_type="PREFERENCE_MEM_UPDATED",
                    source="preference_demo_seed",
                    summary=f"Demo preference recorded: {selected}",
                    payload_dict={
                        "decision": "APPROVED",
                        "selected_profile": selected,
                        "personalized_profile": preferred,
                        "total_runs": index + 1,
                        "profile_counts": profile_counts,
                        "learned_constraints": memory.learned_constraints,
                        "seeded": True,
                    },
                    state_version=1,
                )

    print(
        json.dumps(
            {
                "status": "seeded",
                "preferred_profile": preferred,
                "preferred_count": args.preferred_count,
                "total_decisions": args.decisions,
                "backup_path": str(args.backup_path),
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    validate_args(args)
    plan = {
        "preferred_profile": args.profile,
        "preferred_count": args.preferred_count,
        "total_decisions": args.decisions,
        "backup_path": str(args.backup_path),
    }
    if not args.apply:
        print(json.dumps({"status": "dry-run", **plan}, indent=2))
        print("Run again with --apply to write this demo preference history.")
        return
    asyncio.run(seed(args))


if __name__ == "__main__":
    main()
