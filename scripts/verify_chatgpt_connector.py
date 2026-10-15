#!/usr/bin/env python3
"""Validate ChatGPT/GitHub connector contract; no API calls or network access."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "integration" / "chatgpt_connector_contract.json"


def verify(data):
    if set(data) != {"schema_version", "repository", "branch", "mode", "execution",
                     "openai_api_required", "github_actions_required_for_reads",
                     "read_only_queries", "constraints"}:
        raise ValueError("Invalid contract fields")
    if data["schema_version"] != 1 or data["mode"] != "chatgpt_github_connector":
        raise ValueError("Unsupported integration contract")
    if data["execution"] != "chatgpt_initiated_only" or data["openai_api_required"] is not False:
        raise ValueError("Paid or autonomous AI integration is prohibited")
    if data["github_actions_required_for_reads"] is not False:
        raise ValueError("GitHub Actions must not be required for simple reads")
    if not isinstance(data["repository"], str) or "/" not in data["repository"]:
        raise ValueError("Invalid repository")
    if data["branch"] != "main":
        raise ValueError("Unexpected branch")
    paths = data["read_only_queries"]
    if not isinstance(paths, dict) or not paths:
        raise ValueError("Missing read paths")
    for value in paths.values():
        if not isinstance(value, str) or value.startswith("/") or ".." in Path(value).parts:
            raise ValueError("Unsafe read path")
    if not isinstance(data["constraints"], list) or len(data["constraints"]) < 5:
        raise ValueError("Missing safety constraints")
    return {"schema_version": 1, "valid": True, "openai_api_required": False,
            "github_actions_required_for_reads": False}


def main():
    try:
        result = verify(json.loads(CONTRACT.read_text(encoding="utf-8")))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
