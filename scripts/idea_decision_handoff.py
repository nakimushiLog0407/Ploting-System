#!/usr/bin/env python3
"""User-confirmed candidate decision handoff. Never infer approval."""
import argparse
import json
import sys
from decision_store import candidate, record, all_decisions, verify_all


def preview_decision(candidate_id, decision, reason=""):
    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be approved or rejected")
    if not isinstance(reason, str) or len(reason) > 20000:
        raise ValueError("Invalid reason")
    verify_all()
    item, digest = candidate(candidate_id)
    if any(existing["candidate_id"] == candidate_id for _, existing in all_decisions()):
        raise ValueError("Candidate already has a decision")
    evidence = item["evidence"]
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": digest,
        "kind": item["kind"],
        "content": item["content"],
        "source_id": evidence["source_id"],
        "source_quote": evidence["quote"],
        "decision_requested": decision,
        "reason": reason,
        "requires_explicit_user_confirmation": True,
        "saved": False,
        "read_only": True,
    }


def decide(candidate_id, decision, reason, request_id, confirmed=False, recorder=None):
    if confirmed is not True:
        raise ValueError("Explicit user confirmation of the decision is required")
    preview = preview_decision(candidate_id, decision, reason)
    persist = record if recorder is None else recorder
    result = persist(request_id, candidate_id, decision, reason, True)
    return {
        "decision_result": result,
        "candidate_id": candidate_id,
        "decision": decision,
        "candidate_sha256": preview["candidate_sha256"],
        "user_confirmed": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Review or explicitly record a candidate decision")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "record"):
        p = sub.add_parser(name)
        p.add_argument("--candidate-id", required=True)
        p.add_argument("--decision", choices=("approved", "rejected"), required=True)
        p.add_argument("--reason", default="")
        if name == "record":
            p.add_argument("--request-id", required=True)
            p.add_argument("--confirm-user-decision", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preview":
            output = preview_decision(args.candidate_id, args.decision, args.reason)
        else:
            output = decide(args.candidate_id, args.decision, args.reason,
                            args.request_id, args.confirm_user_decision)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
