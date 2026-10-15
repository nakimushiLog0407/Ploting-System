#!/usr/bin/env python3
"""Stable read-only JSON interface for ChatGPT-facing project queries.

No implicit writes, no approval operations, no unapproved text as canon.
"""
import argparse
import json
import sys

from candidate_store import all_records
from decision_store import all_decisions, verify_all as verify_decisions
from canon_catalog import build_catalog
from plot_cards import records as card_records
from plot_moves import records as move_records, effective as effective_cards
from scene_links import records as link_records
from foreshadowing import records as thread_records
from foreshadowing_changes import records as change_records, effective as effective_threads
from plot_diagnostics import diagnose as diagnose_plot
from plot_diagnostic_review import overview as plot_review_overview
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records
from prose_diagnostics import diagnose as diagnose_prose
from prose_diagnostic_review import overview as prose_review_overview
from writing_progress import summarize as writing_progress
from review_inbox import build as review_inbox
from project_dashboard import build as project_dashboard
from manuscript_export import assemble as manuscript_assemble, render_text
from writing_context import build as writing_context


def snapshot():
    verify_decisions()
    candidates = [x for _, x in all_records()]
    decisions = [x for _, x in all_decisions()]
    cards = card_records()
    moves = move_records(cards)
    effective = effective_cards(cards, moves)
    links = link_records(cards)
    threads = thread_records(cards)
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    changes = change_records(threads, scenes)
    plot_findings = diagnose_plot(effective, links, effective_threads(threads, changes, scenes))["findings"]
    drafts = draft_records(cards)
    revisions = revision_records(drafts)
    prose_findings = diagnose_prose(cards, moves, drafts, revisions)["findings"]
    return {
        "candidates": candidates, "decisions": decisions, "cards": cards,
        "moves": moves, "drafts": drafts, "revisions": revisions,
        "plot_review": plot_review_overview(plot_findings),
        "prose_review": prose_review_overview(prose_findings),
    }


def query(command, data, scene_id=None, previous_scenes=2, max_prose_chars=6000):
    cards, moves = data["cards"], data["moves"]
    drafts, revisions = data["drafts"], data["revisions"]
    if command == "dashboard":
        result = project_dashboard(data["candidates"], data["decisions"], cards, moves,
                                   drafts, revisions, data["plot_review"], data["prose_review"])
    elif command == "inbox":
        result = review_inbox(data["candidates"], data["decisions"], cards, drafts,
                              revisions, data["plot_review"], data["prose_review"])
    elif command == "progress":
        result = writing_progress(cards, moves, drafts, revisions)
    elif command == "manuscript":
        result = manuscript_assemble(cards, moves, drafts, revisions)
    elif command == "context":
        if not scene_id:
            raise ValueError("context requires --scene-id")
        result = writing_context(scene_id, cards, moves, drafts, revisions,
                                 build_catalog(), None, previous_scenes, max_prose_chars)
    else:
        raise ValueError("Unsupported command")
    return {"interface_version": 1, "command": command, "data": result,
            "read_only": True, "approval_performed": False}


def main():
    p = argparse.ArgumentParser(description="Read-only unified project query interface")
    p.add_argument("command", choices=("dashboard", "inbox", "progress", "manuscript", "context"))
    p.add_argument("--scene-id")
    p.add_argument("--previous-scenes", type=int, default=2)
    p.add_argument("--max-prose-chars", type=int, default=6000)
    p.add_argument("--format", choices=("json", "text"), default="json")
    args = p.parse_args()
    try:
        if args.format == "text" and args.command != "manuscript":
            raise ValueError("Text output is only available for manuscript")
        data = query(args.command, snapshot(), args.scene_id, args.previous_scenes,
                     args.max_prose_chars)
        if args.format == "text":
            print(render_text(data["data"]), end="")
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
