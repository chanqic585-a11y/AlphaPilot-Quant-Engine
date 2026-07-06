from __future__ import annotations

import json

from alphapilot.artifacts.strategy_artifact_index import generate_strategy_artifact_index


def main() -> None:
    payload = generate_strategy_artifact_index()
    print(
        json.dumps(
            {
                "version": payload["version"],
                "source": payload["source"],
                "generatedAt": payload["generatedAt"],
                "output": "reports/strategy_artifact_index.json",
                "summary": payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

