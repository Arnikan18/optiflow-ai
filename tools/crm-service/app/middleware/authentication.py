from fastapi import Header, HTTPException, status
from app.config import settings

def verify_tool_token(
    x_tool_token: str | None = Header(default=None, alias="X-Tool-Token"),
) -> None:
    if x_tool_token != settings.tool_shared_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tool-service token",
        )
