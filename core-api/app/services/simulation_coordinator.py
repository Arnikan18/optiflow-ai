import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("core-api.services.simulation_coordinator")

class SimulationCoordinator:
    """Orchestrator separating AI workflows from Simulation backend transport mechanism.
    
    Exposes complete callback interfaces matching simulation lifecycle events.
    """
    _notifier: Optional[Any] = None

    @classmethod
    def register_notifier(cls, notifier: Any) -> None:
        """Injects a concrete transport notifier implementation (e.g. HTTP, WebSockets, or Mock)."""
        cls._notifier = notifier
        logger.info(f"Registered simulation notifier: {notifier}")

    @classmethod
    async def on_simulation_started(cls, scenario_id: str, mode: str) -> None:
        """Invoked when simulation setup initiates."""
        if cls._notifier and hasattr(cls._notifier, "on_simulation_started"):
            try:
                await cls._notifier.on_simulation_started(scenario_id, mode)
            except Exception as e:
                logger.error(f"Notifier error in on_simulation_started: {e}")

    @classmethod
    async def on_enterprise_change(cls, event: Dict[str, Any], current_state: Dict[str, Any]) -> None:
        """Invoked when a simulation event shifts the operational state."""
        if cls._notifier and hasattr(cls._notifier, "on_enterprise_change"):
            try:
                await cls._notifier.on_enterprise_change(event, current_state)
            except Exception as e:
                logger.error(f"Notifier error in on_enterprise_change: {e}")

    @classmethod
    async def on_execution_complete(cls, run_id: str, timeline_position: int, state: Dict[str, Any]) -> None:
        """Invoked upon successful plan execution to notify the simulation workflow."""
        if cls._notifier and hasattr(cls._notifier, "on_execution_complete"):
            try:
                await cls._notifier.on_execution_complete(run_id, timeline_position, state)
            except Exception as e:
                logger.error(f"Notifier error in on_execution_complete: {e}")
