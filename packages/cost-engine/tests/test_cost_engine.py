from cost_engine import (
    aggregate_events,
    approx_token_count,
    estimate_cost,
    estimate_messages_tokens,
    list_models,
    load_price_table,
    reconcile_usage,
)


def test_load_price_table_has_core_models():
    table = load_price_table()
    assert "gpt-4o-mini" in table
    assert "claude-3-5-haiku-20241022" in table
    assert "gemini-2.0-flash" in table


def test_estimate_cost_known_model():
    cost = estimate_cost("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost.provider == "openai"
    assert cost.input_cost_usd == 0.15
    assert cost.output_cost_usd == 0.6
    assert cost.total_cost_usd == 0.75


def test_estimate_cost_unknown_model_zero():
    cost = estimate_cost("unknown-model-xyz", 1000, 1000)
    assert cost.provider == "unknown"
    assert cost.total_cost_usd == 0.0


def test_reconcile_usage_openai_shape():
    cost = reconcile_usage(
        "gpt-4o-mini",
        {"prompt_tokens": 1000, "completion_tokens": 500},
    )
    assert cost.input_tokens == 1000
    assert cost.output_tokens == 500
    assert cost.total_cost_usd > 0


def test_approx_and_messages_tokens():
    assert approx_token_count("abcd") == 1
    tokens = estimate_messages_tokens(
        [{"role": "user", "content": "hello world this is a test message"}]
    )
    assert tokens > 0


def test_aggregate_events():
    events = [
        {"model": "a", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.01, "cache_hit": False},
        {"model": "a", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.02, "cache_hit": True},
        {"model": "b", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.05, "cache_hit": False},
    ]
    aggs = aggregate_events(events, group_by="model")
    assert aggs[0].key == "b"
    assert aggs[1].key == "a"
    assert aggs[1].cache_hits == 1
    assert aggs[1].request_count == 2


def test_list_models():
    models = list_models()
    assert len(models) >= 5
