from math import ceil
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SimulationEventHistory, SimulationNotification, SimulationRun
from app.simulation.enterprise_event_engine import EnterpriseEventEngine, get_event_engine
from app.simulation.scenario_loader import ScenarioLoader, get_scenario_loader
from app.simulation.schemas import (
    AdvanceSimulationData,
    EventHistoryData,
    NotificationListData,
    NotificationStatus,
    ScenarioBundle,
    SimulationError,
    SimulationMode,
    SimulationStatus,
    StartSimulationData,
    StartSimulationRequest,
    SimulationStatusData,
    utc_now,
)


ACTIVE_STATUSES = {SimulationStatus.RUNNING.value, SimulationStatus.PAUSED.value}


class TimelineSimulator:
    def __init__(
        self,
        loader: ScenarioLoader | None = None,
        event_engine: EnterpriseEventEngine | None = None,
    ) -> None:
        self.loader = loader or get_scenario_loader()
        self.event_engine = event_engine or get_event_engine()

    async def start(
        self,
        session: AsyncSession,
        payload: StartSimulationRequest,
        *,
        request_id: str,
    ) -> StartSimulationData:
        active = await self._active_run(session)
        if active is not None and not payload.reset_existing:
            raise SimulationError(409, "SIMULATION_ALREADY_RUNNING", "A simulation is already active")

        scenario = self.loader.load_scenario(payload.scenario_id)
        if active is not None:
            active.status = SimulationStatus.STOPPED.value
            active.updated_at = utc_now()
            session.add(active)
            await session.flush()

        await self.event_engine.load_initial_state(
            scenario_id=scenario.metadata.scenario_id,
            initial_state=scenario.initial_state,
            request_id=request_id,
        )

        enabled_event_ids = [event.event_id for event in scenario.timeline if event.enabled]
        first_event = self._next_event(scenario, 0)
        now = utc_now()
        run = SimulationRun(
            simulation_id=f"SIM-{uuid4().hex[:12].upper()}",
            scenario_id=scenario.metadata.scenario_id,
            scenario_name=scenario.metadata.name,
            mode=payload.mode.value,
            status=SimulationStatus.RUNNING.value,
            current_time=scenario.metadata.start_time,
            current_stage=first_event.stage if first_event else scenario.metadata.stages[0],
            current_timeline_position=0,
            processed_events=[],
            pending_events=enabled_event_ids,
            last_event=None,
            enterprise_changed=False,
            notification_status=NotificationStatus.NOT_REQUIRED.value,
            auto_advance=bool(payload.auto_advance),
            started_at=now,
            updated_at=now,
        )
        session.add(run)
        await session.flush()
        return StartSimulationData(**self._run_status(run), next_event=self._event_preview(first_event))

    async def pause(self, session: AsyncSession) -> SimulationStatusData:
        run = await self._required_active_run(session)
        if run.status != SimulationStatus.RUNNING.value:
            raise SimulationError(409, "SIMULATION_INVALID_STATE", "Only a running simulation can be paused")
        run.status = SimulationStatus.PAUSED.value
        run.paused_at = utc_now()
        run.updated_at = utc_now()
        session.add(run)
        await session.flush()
        return SimulationStatusData(**self._run_status(run))

    async def resume(self, session: AsyncSession) -> SimulationStatusData:
        run = await self._required_active_run(session)
        if run.status != SimulationStatus.PAUSED.value:
            raise SimulationError(409, "SIMULATION_INVALID_STATE", "Only a paused simulation can be resumed")
        run.status = SimulationStatus.RUNNING.value
        run.paused_at = None
        run.updated_at = utc_now()
        session.add(run)
        await session.flush()
        return SimulationStatusData(**self._run_status(run))

    async def stop(self, session: AsyncSession) -> SimulationStatusData:
        run = await self._required_active_run(session)
        run.status = SimulationStatus.STOPPED.value
        run.updated_at = utc_now()
        session.add(run)
        await session.flush()
        return SimulationStatusData(**self._run_status(run))

    async def reset(
        self,
        session: AsyncSession,
        *,
        scenario_id: str | None,
        request_id: str,
    ) -> SimulationStatusData:
        scenario = self.loader.load_scenario(scenario_id)
        await self.event_engine.load_initial_state(
            scenario_id=scenario.metadata.scenario_id,
            initial_state=scenario.initial_state,
            request_id=request_id,
        )

        active = await self._active_run(session)
        if active is not None:
            active.status = SimulationStatus.STOPPED.value
            active.current_timeline_position = 0
            active.current_time = scenario.metadata.start_time
            active.current_stage = scenario.metadata.stages[0]
            active.processed_events = []
            active.pending_events = [event.event_id for event in scenario.timeline if event.enabled]
            active.last_event = None
            active.enterprise_changed = False
            active.notification_status = NotificationStatus.NOT_REQUIRED.value
            active.completed_at = None
            active.paused_at = None
            active.updated_at = utc_now()
            session.add(active)

        await session.execute(delete(SimulationNotification))
        await session.execute(delete(SimulationEventHistory))
        await session.flush()
        return SimulationStatusData(
            simulation_id=None,
            scenario_id=scenario.metadata.scenario_id,
            scenario_name=scenario.metadata.name,
            mode=None,
            status=SimulationStatus.IDLE,
            current_time=scenario.metadata.start_time,
            current_stage=scenario.metadata.stages[0],
            current_timeline_position=0,
            processed_events=[],
            pending_events=[event.event_id for event in scenario.timeline if event.enabled],
            last_event=None,
            enterprise_changed=False,
            notification_status=NotificationStatus.NOT_REQUIRED,
            started_at=None,
            paused_at=None,
            completed_at=None,
            updated_at=utc_now(),
        )

    async def advance(self, session: AsyncSession, *, request_id: str) -> AdvanceSimulationData:
        run = await self._required_active_run(session)
        if run.mode != SimulationMode.TIMELINE.value:
            raise SimulationError(409, "SIMULATION_INVALID_MODE", "Timeline advancement requires TIMELINE mode")
        if run.status == SimulationStatus.PAUSED.value:
            raise SimulationError(409, "SIMULATION_PAUSED", "Paused simulations cannot be advanced")
        if run.status != SimulationStatus.RUNNING.value:
            raise SimulationError(409, "SIMULATION_INVALID_STATE", "Only a running simulation can be advanced")

        scenario = self.loader.load_scenario(run.scenario_id)
        next_event = self._next_event(scenario, run.current_timeline_position)
        if next_event is None:
            run.status = SimulationStatus.COMPLETED.value
            run.completed_at = utc_now()
            run.updated_at = utc_now()
            session.add(run)
            await session.flush()
            return AdvanceSimulationData(
                **self._run_status(run),
                processed_event=None,
                next_event=None,
                completed=True,
            )

        result = await self.event_engine.process_timeline_event(
            session,
            next_event,
            simulation_id=run.simulation_id,
            request_id=request_id,
            current_stage=next_event.stage,
        )
        processed_events = list(run.processed_events or [])
        if next_event.event_id not in processed_events:
            processed_events.append(next_event.event_id)
        next_position = self._index_after_event(scenario, next_event.event_id)
        pending_events = [
            event.event_id
            for event in scenario.timeline[next_position:]
            if event.enabled and event.event_id not in processed_events
        ]
        following_event = self._next_event(scenario, next_position)
        completed = following_event is None

        run.current_time = next_event.scheduled_time
        run.current_stage = next_event.stage
        run.current_timeline_position = next_position
        run.processed_events = processed_events
        run.pending_events = pending_events
        run.last_event = result.model_dump(mode="json")
        run.enterprise_changed = result.enterprise_changed
        run.notification_status = result.notification_status.value
        if completed:
            run.status = SimulationStatus.COMPLETED.value
            run.completed_at = utc_now()
        run.updated_at = utc_now()
        session.add(run)
        await session.flush()

        return AdvanceSimulationData(
            **self._run_status(run),
            processed_event=self._event_preview(next_event),
            next_event=self._event_preview(following_event),
            completed=completed,
        )

    async def status(self, session: AsyncSession) -> SimulationStatusData:
        run = await self._latest_run(session)
        if run is None:
            scenario_id = self.loader.determine_default_scenario_id(self.loader.list_scenarios().scenarios)
            scenario = self.loader.load_scenario(scenario_id) if scenario_id else None
            return self._idle_status(scenario)
        return SimulationStatusData(**self._run_status(run))

    async def list_event_history(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        simulation_id: str | None = None,
    ) -> EventHistoryData:
        events, total = await self.event_engine.list_event_history(
            session,
            page=page,
            page_size=page_size,
            simulation_id=simulation_id,
        )
        total_pages = ceil(total / page_size) if total else 0
        return EventHistoryData(events=events, page=page, page_size=page_size, total_items=total, total_pages=total_pages)

    async def list_notifications(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> NotificationListData:
        notifications, total = await self.event_engine.list_notifications(
            session,
            page=page,
            page_size=page_size,
            status=status,
        )
        total_pages = ceil(total / page_size) if total else 0
        return NotificationListData(
            notifications=notifications,
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        )

    async def acknowledge_notification(self, session: AsyncSession, notification_id: str) -> dict[str, Any]:
        return await self.event_engine.acknowledge_notification(session, notification_id)

    async def inject_event(
        self,
        session: AsyncSession,
        request,
        *,
        request_id: str,
    ):
        run = await self._latest_run(session)
        current_stage = run.current_stage if run else None
        current_time = run.current_time if run else None
        simulation_id = run.simulation_id if run else None
        if run is not None and request.scenario_id is None:
            request.scenario_id = run.scenario_id
        return await self.event_engine.process_event(
            session,
            request,
            simulation_id=simulation_id,
            request_id=request_id,
            current_stage=current_stage,
            current_simulation_time=current_time,
        )

    async def _active_run(self, session: AsyncSession) -> SimulationRun | None:
        result = await session.execute(
            select(SimulationRun)
            .where(SimulationRun.status.in_(ACTIVE_STATUSES))
            .order_by(desc(SimulationRun.started_at), desc(SimulationRun.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _required_active_run(self, session: AsyncSession) -> SimulationRun:
        run = await self._active_run(session)
        if run is None:
            raise SimulationError(409, "SIMULATION_NOT_ACTIVE", "No active simulation is available")
        return run

    async def _latest_run(self, session: AsyncSession) -> SimulationRun | None:
        result = await session.execute(
            select(SimulationRun).order_by(desc(SimulationRun.started_at), desc(SimulationRun.updated_at)).limit(1)
        )
        return result.scalar_one_or_none()

    def _next_event(self, scenario: ScenarioBundle, start_position: int):
        for event in scenario.timeline[start_position:]:
            if event.enabled:
                return event
        return None

    def _index_after_event(self, scenario: ScenarioBundle, event_id: str) -> int:
        for index, event in enumerate(scenario.timeline):
            if event.event_id == event_id:
                return index + 1
        return len(scenario.timeline)

    def _event_preview(self, event) -> dict[str, Any] | None:
        if event is None:
            return None
        return {
            "event_id": event.event_id,
            "scenario_id": event.scenario_id,
            "scheduled_time": event.scheduled_time,
            "stage": event.stage,
            "event_type": event.event_type.value,
            "description": event.description,
            "sequence": event.sequence,
            "enabled": event.enabled,
        }

    def _idle_status(self, scenario: ScenarioBundle | None) -> SimulationStatusData:
        return SimulationStatusData(
            simulation_id=None,
            scenario_id=scenario.metadata.scenario_id if scenario else None,
            scenario_name=scenario.metadata.name if scenario else None,
            mode=None,
            status=SimulationStatus.IDLE,
            current_time=scenario.metadata.start_time if scenario else None,
            current_stage=scenario.metadata.stages[0] if scenario else None,
            current_timeline_position=0,
            processed_events=[],
            pending_events=[event.event_id for event in scenario.timeline if event.enabled] if scenario else [],
            last_event=None,
            enterprise_changed=False,
            notification_status=NotificationStatus.NOT_REQUIRED,
            started_at=None,
            paused_at=None,
            completed_at=None,
            updated_at=None,
        )

    def _run_status(self, run: SimulationRun) -> dict[str, Any]:
        return {
            "simulation_id": run.simulation_id,
            "scenario_id": run.scenario_id,
            "scenario_name": run.scenario_name,
            "mode": SimulationMode(run.mode),
            "status": SimulationStatus(run.status),
            "current_time": run.current_time,
            "current_stage": run.current_stage,
            "current_timeline_position": run.current_timeline_position,
            "processed_events": run.processed_events or [],
            "pending_events": run.pending_events or [],
            "last_event": run.last_event,
            "enterprise_changed": run.enterprise_changed,
            "notification_status": NotificationStatus(run.notification_status),
            "started_at": run.started_at,
            "paused_at": run.paused_at,
            "completed_at": run.completed_at,
            "updated_at": run.updated_at,
        }


_simulator: TimelineSimulator | None = None


def get_timeline_simulator() -> TimelineSimulator:
    global _simulator
    if _simulator is None:
        _simulator = TimelineSimulator()
    return _simulator
