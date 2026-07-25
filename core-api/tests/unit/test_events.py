import pytest
import asyncio
from app.agent.events import EventPublisher

@pytest.mark.asyncio
async def test_event_publisher_pub_sub():
    publisher = EventPublisher()
    run_id = "RUN-TEST-EVENT"
    
    # 1. Subscribe
    queue = publisher.subscribe(run_id)
    assert queue.empty()
    
    # 2. Publish
    event = {"sequence_number": 1, "event_type": "TEST_EVENT", "source": "test", "summary": "test message"}
    publisher.publish(run_id, event)
    
    # 3. Retrieve
    assert not queue.empty()
    retrieved = await queue.get()
    assert retrieved == event
    queue.task_done()
    
    # 4. Unsubscribe
    publisher.unsubscribe(run_id, queue)
    # Publish again - should not put anything in queue
    publisher.publish(run_id, {"sequence_number": 2})
    assert queue.empty()

def test_sse_streaming_route():
    from fastapi.testclient import TestClient
    from app.main import app
    from unittest.mock import patch, MagicMock
    
    client = TestClient(app)
    
    # Mock database historical query response to return empty list
    with patch("app.main.async_session") as mock_session_cls, \
         patch("app.agent.events.event_publisher") as mock_publisher:
         
        mock_session = MagicMock()
        mock_execute = MagicMock()
        mock_execute.fetchall.return_value = []
        
        from unittest.mock import AsyncMock
        mock_session.execute = AsyncMock(return_value=mock_execute)
        
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        # Mock active subscriber queue to raise CancelledError immediately to stop streaming generator
        mock_queue = MagicMock()
        async def mock_get():
            raise asyncio.CancelledError()
        mock_queue.get = mock_get
        mock_publisher.subscribe.return_value = mock_queue
        
        response = client.get("/api/v1/runs/RUN-TEST-EVENT/stream")
        assert response.status_code == 200
        # Starlette EventSourceResponse content type is text/event-stream
        assert "text/event-stream" in response.headers["content-type"]
