from __future__ import annotations

DEFAULT_ALIASES: dict[str, str] = {
    "autopilot/cheap": "gpt-4o-mini",
    "autopilot/balanced": "gpt-4o",
    "autopilot/quality": "claude-sonnet-4-20250514",
    "autopilot/fast": "gemini-2.0-flash",
}


def resolve_model(requested: str, org_overrides: dict[str, str] | None = None) -> str:
    overrides = org_overrides or {}
    if requested in overrides:
        return overrides[requested]
    if requested in DEFAULT_ALIASES:
        return DEFAULT_ALIASES[requested]
    return requested
