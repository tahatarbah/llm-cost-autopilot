from gateway.routing import resolve_model


def test_estimate_cost_alias_resolution_matches_router():
    assert resolve_model("autopilot/fast") == "gemini-2.0-flash"
