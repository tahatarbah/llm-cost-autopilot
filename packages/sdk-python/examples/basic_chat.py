"""Example: call the gateway via the Autopilot SDK.

Usage:
  set LCA_API_KEY=...
  python examples/basic_chat.py
"""

from __future__ import annotations

import os
import sys

from llm_cost_sdk import AutopilotClient


def main() -> int:
    api_key = os.environ.get("LCA_API_KEY")
    if not api_key:
        print("Set LCA_API_KEY to your virtual gateway key (from llm-cost-seed).", file=sys.stderr)
        return 1

    base = os.environ.get("LCA_BASE_URL", "http://localhost:8080/v1")
    with AutopilotClient(api_key, base_url=base) as client:
        estimate = client.estimate(
            "autopilot/cheap",
            [{"role": "user", "content": "Say hello in one sentence."}],
        )
        print("Estimate:", estimate)

        result = client.chat_completions(
            model="autopilot/cheap",
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
            max_tokens=64,
        )
        content = result["choices"][0]["message"]["content"]
        print("Reply:", content)
        print("Autopilot meta:", result.get("_autopilot"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
