import asyncio
import logging
from typing import Dict, Any, List

logger = logging.getLogger("core-api.agent.events")

class EventPublisher:
    """In-memory event publishing broker linking persistent state changes to SSE connections."""
    def __init__(self):
        # Map run_id -> List of active asyncio Queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribes an asyncio Queue to receive run_events stream for the given run_id."""
        queue = asyncio.Queue()
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(queue)
        logger.debug(f"Subscriber registered for run {run_id}. Total: {len(self._subscribers[run_id])}")
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Removes the subscriber queue from the active subscribers list."""
        if run_id in self._subscribers:
            try:
                self._subscribers[run_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]
            logger.debug(f"Subscriber removed for run {run_id}")

    def publish(self, run_id: str, event_data: Dict[str, Any]) -> None:
        """Publishes the event message to all registered subscriber queues of this run."""
        if run_id in self._subscribers:
            logger.debug(f"Broadcasting event to {len(self._subscribers[run_id])} subscribers for {run_id}")
            for queue in self._subscribers[run_id]:
                queue.put_nowait(event_data)

# Singleton broker instance
event_publisher = EventPublisher()
