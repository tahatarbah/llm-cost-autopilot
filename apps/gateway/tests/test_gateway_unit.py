"""Gateway unit tests (no live provider keys)."""

from __future__ import annotations

import hashlib

from gateway.cache import cache_key
from gateway.db.models import generate_api_key, hash_api_key


def test_api_key_hash_stable():
    raw, prefix, digest = generate_api_key()
    assert raw.startswith("lca_")
    assert prefix == raw[:12]
    assert digest == hash_api_key(raw)
    assert digest == hashlib.sha256(raw.encode()).hexdigest()


def test_cache_key_deterministic():
    a = cache_key("m", [{"role": "user", "content": "hi"}], temperature=0.2)
    b = cache_key("m", [{"role": "user", "content": "hi"}], temperature=0.2)
    c = cache_key("m", [{"role": "user", "content": "bye"}], temperature=0.2)
    assert a == b
    assert a != c
