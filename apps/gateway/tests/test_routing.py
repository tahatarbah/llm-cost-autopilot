from gateway.routing import resolve_model, DEFAULT_ALIASES


def test_default_aliases():
    assert resolve_model("autopilot/cheap") == "gpt-4o-mini"
    assert resolve_model("autopilot/balanced") == "gpt-4o"
    assert "autopilot/quality" in DEFAULT_ALIASES


def test_org_override_wins():
    assert resolve_model("autopilot/cheap", {"autopilot/cheap": "gemini-2.0-flash"}) == "gemini-2.0-flash"


def test_passthrough_concrete_model():
    assert resolve_model("gpt-4.1-mini") == "gpt-4.1-mini"
