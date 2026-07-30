import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config.settings import settings
from app.simulation.schemas import (
    InitialState,
    ScenarioBundle,
    ScenarioListData,
    ScenarioMetadata,
    SimulationError,
    TimelineEvent,
)


REQUIRED_SCENARIO_FILES = ("metadata.json", "initial_state.json", "timeline.json")


def resolve_scenario_root(configured_path: str | None = None) -> Path:
    configured = configured_path or settings.simulation_scenario_root
    candidates: list[Path] = []
    if configured:
        path = Path(configured)
        candidates.append(path if path.is_absolute() else Path.cwd() / path)
        candidates.append(path if path.is_absolute() else Path.cwd().parent / path)

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "scenarios")
    candidates.append(Path.cwd() / "scenarios")

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


class ScenarioLoader:
    def __init__(self, scenario_root: Path | None = None, default_scenario_id: str | None = None) -> None:
        self.scenario_root = (scenario_root or resolve_scenario_root()).resolve()
        self.default_scenario_id = default_scenario_id or settings.simulation_default_scenario
        self._cache: dict[str, ScenarioBundle] = {}
        self._folder_by_scenario_id: dict[str, Path] = {}

    def reload(self) -> None:
        self._cache.clear()
        self._folder_by_scenario_id.clear()

    def list_scenarios(self, *, reload: bool = False) -> ScenarioListData:
        if reload:
            self.reload()
        scenarios = [self.load_metadata_from_folder(folder) for folder in self._valid_folders()]
        self._reject_duplicate_scenario_ids(scenarios)
        scenarios.sort(key=lambda item: item.scenario_id)
        return ScenarioListData(
            scenarios=scenarios,
            default_scenario_id=self.determine_default_scenario_id(scenarios),
        )

    def get_metadata(self, scenario_id: str) -> ScenarioMetadata:
        scenario_id = scenario_id.strip()
        bundle = self._cache.get(scenario_id)
        if bundle is not None:
            return bundle.metadata

        for metadata in self.list_scenarios().scenarios:
            if metadata.scenario_id == scenario_id:
                return metadata
        raise SimulationError(404, "SIMULATION_SCENARIO_NOT_FOUND", "Scenario not found")

    def load_scenario(self, scenario_id: str | None = None, *, reload: bool = False) -> ScenarioBundle:
        if reload:
            self.reload()
        scenario_id = scenario_id or self.determine_default_scenario_id(self.list_scenarios().scenarios)
        if not scenario_id:
            raise SimulationError(404, "SIMULATION_NO_SCENARIOS", "No scenarios are available")
        if scenario_id in self._cache:
            return self._cache[scenario_id]

        folder = self._folder_for_scenario_id(scenario_id)
        metadata = self.load_metadata_from_folder(folder)
        initial_state = self._load_model(folder / "initial_state.json", InitialState)
        timeline_items = self._load_json(folder / "timeline.json")
        if not isinstance(timeline_items, list):
            raise SimulationError(
                422,
                "SIMULATION_SCENARIO_INVALID",
                "timeline.json must contain a list of events",
                details=[{"file": str(folder / "timeline.json")}],
            )
        timeline = [self._parse_model(item, TimelineEvent, folder / "timeline.json") for item in timeline_items]
        bundle = self._parse_model(
            {
                "metadata": metadata,
                "initial_state": initial_state,
                "timeline": timeline,
                "folder_name": folder.name,
            },
            ScenarioBundle,
            folder,
        )
        self._cache[bundle.metadata.scenario_id] = bundle
        return bundle

    def validate_scenario(self, scenario_id: str) -> ScenarioBundle:
        return self.load_scenario(scenario_id, reload=True)

    def load_metadata_from_folder(self, folder: Path) -> ScenarioMetadata:
        self._validate_folder(folder)
        return self._load_model(folder / "metadata.json", ScenarioMetadata)

    def determine_default_scenario_id(self, scenarios: list[ScenarioMetadata] | None = None) -> str | None:
        scenarios = scenarios if scenarios is not None else self.list_scenarios().scenarios
        if not scenarios:
            return None
        scenario_ids = {scenario.scenario_id for scenario in scenarios}
        if self.default_scenario_id:
            if self.default_scenario_id not in scenario_ids:
                raise SimulationError(
                    422,
                    "SIMULATION_DEFAULT_SCENARIO_INVALID",
                    "Configured default scenario was not found",
                    details=[{"scenario_id": self.default_scenario_id}],
                )
            return self.default_scenario_id
        return sorted(scenario_ids)[0]

    def _valid_folders(self) -> list[Path]:
        if not self.scenario_root.exists():
            raise SimulationError(
                503,
                "SIMULATION_SCENARIO_ROOT_MISSING",
                "Scenario repository is not available",
                details=[{"path": str(self.scenario_root)}],
            )
        folders = [path for path in self.scenario_root.iterdir() if path.is_dir()]
        valid: list[Path] = []
        for folder in folders:
            present = [name for name in REQUIRED_SCENARIO_FILES if (folder / name).exists()]
            if present and len(present) != len(REQUIRED_SCENARIO_FILES):
                self._validate_folder(folder)
            if len(present) == len(REQUIRED_SCENARIO_FILES):
                valid.append(folder)
        valid.sort(key=lambda item: item.name)
        return valid

    def _folder_for_scenario_id(self, scenario_id: str) -> Path:
        if scenario_id in self._folder_by_scenario_id:
            return self._folder_by_scenario_id[scenario_id]

        matched: list[Path] = []
        metadata_by_folder: list[ScenarioMetadata] = []
        for folder in self._valid_folders():
            metadata = self.load_metadata_from_folder(folder)
            metadata_by_folder.append(metadata)
            self._folder_by_scenario_id[metadata.scenario_id] = folder
            if metadata.scenario_id == scenario_id:
                matched.append(folder)
        self._reject_duplicate_scenario_ids(metadata_by_folder)
        if not matched:
            raise SimulationError(404, "SIMULATION_SCENARIO_NOT_FOUND", "Scenario not found")
        return matched[0]

    def _validate_folder(self, folder: Path) -> None:
        missing = [name for name in REQUIRED_SCENARIO_FILES if not (folder / name).exists()]
        if missing:
            raise SimulationError(
                422,
                "SIMULATION_SCENARIO_INCOMPLETE",
                "Scenario folder is missing required files",
                details=[{"folder": str(folder), "missing": missing}],
            )

    def _reject_duplicate_scenario_ids(self, scenarios: list[ScenarioMetadata]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for scenario in scenarios:
            if scenario.scenario_id in seen:
                duplicates.add(scenario.scenario_id)
            seen.add(scenario.scenario_id)
        if duplicates:
            raise SimulationError(
                422,
                "SIMULATION_DUPLICATE_SCENARIO_ID",
                "Scenario repository contains duplicate scenario IDs",
                details=[{"scenario_ids": sorted(duplicates)}],
            )

    def _load_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SimulationError(
                422,
                "SIMULATION_SCENARIO_JSON_INVALID",
                "Scenario file contains malformed JSON",
                details=[{"file": str(path), "line": exc.lineno, "column": exc.colno}],
            ) from exc
        except OSError as exc:
            raise SimulationError(
                503,
                "SIMULATION_SCENARIO_READ_FAILED",
                "Scenario file could not be read",
                details=[{"file": str(path)}],
            ) from exc

    def _load_model(self, path: Path, model_type: type[ScenarioMetadata] | type[InitialState]) -> Any:
        return self._parse_model(self._load_json(path), model_type, path)

    def _parse_model(self, data: Any, model_type: type[Any], path: Path) -> Any:
        try:
            return model_type.model_validate(data)
        except ValidationError as exc:
            raise SimulationError(
                422,
                "SIMULATION_SCENARIO_INVALID",
                "Scenario validation failed",
                details=[
                    {
                        "file": str(path),
                        "field": ".".join(str(part) for part in error.get("loc", ())),
                        "message": str(error.get("msg", "Invalid value")),
                    }
                    for error in exc.errors()
                ],
            ) from exc
        except ValueError as exc:
            raise SimulationError(
                422,
                "SIMULATION_SCENARIO_INVALID",
                "Scenario validation failed",
                details=[{"file": str(path), "message": str(exc)}],
            ) from exc


_loader: ScenarioLoader | None = None


def get_scenario_loader() -> ScenarioLoader:
    global _loader
    if _loader is None:
        _loader = ScenarioLoader()
    return _loader
