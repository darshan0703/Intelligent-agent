"""
app/intelligence/agent/tools/screen_tools.py
Screen navigation and kiosk capability invocation tools.
"""
from __future__ import annotations
from typing import Any
from app.domain.session.entities import SessionState


class ScreenTools:
    async def perform_screen_action(
        self,
        session: SessionState,
        control: str,
        value: str | None = None,
    ) -> dict[str, Any]:
        if not session.current_screen:
            return {"success": False, "error": "No active screen on kiosk"}

        if control not in session.current_screen.available_controls:
            return {
                "success": False,
                "error": f"Control '{control}' not available on screen '{session.current_screen.name}'",
                "available": session.current_screen.available_controls,
            }

        return {
            "success": True,
            "action": control,
            "value": value,
            "screen": session.current_screen.name,
        }
