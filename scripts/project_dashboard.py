#!/usr/bin/env python3
"""Read-only project overview; no generated prose, approval, or inferred canon."""
import argparse
import json
import sys

from candidate_store import all_records
from decision_store import all_decisions, verify_all as verify_decisions
from plot_cards import records as plot_records
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


def build(candidates, decisions, cards, moves, drafts, revisions, plot_review, prose_review):
    candidate_ids = {x["candidate_id"] for x in candidates}
    decision_by_id = {x["candidate_id"]: x["decision"] for x in decisions}
    if len(candidate_ids) != len(candidates) or len(decision_by_id) != len(decisions):
        raise ValueError("Duplicate candidate or decision ID")
    if not set(decision_by_id).issubset(candidate_ids):
        raise ValueError("Decision references unknown candidate")
    canon = {
        "total": len(candidates),
        "approved": sum(v == "approved" for v in decision_by_id.values()),
        "rejected": sum(v == "rejected" for v in decision_by_id.values()),
        "pending": len(candidates) - len(decision_by_id),
    }
    plot = {
        "total": len(cards),
        "approved": sum(x["status"] == "approved" for x in cards),
        "rejected": sum(x["status"] == "rejected" for x in cards),
        "pending": sum(x["status"] == "proposed" for x in cards),
    }
    writing = writing_progress(cards, moves, drafts, revisions)
    inbox = review_inbox(candidates, decisions, cards, drafts, revisions, plot_review, prose_review)
    return {
        "canon": canon,
        "plot_cards": plot,
        "writing": writing["summary"],
        "unplaced_scene_ids": writing["unplaced_scene_ids"],
        "review_inbox": {"total": inbox["total"], "by_category": inbox["by_category"]},
        "diagnostics": {
            "plot_findings": len(plot_review["findings"]),
            "prose_findings": len(prose_review["findings"]),
        },
        "approval_is_explicit": True,
        "unapproved_content_excluded_from_writing_progress": True,
        "automatic_changes": False,
        "source_records_modified": False,
    }


def collect():
    verify_decisions()
    candidates = [x for _, x in all_records()]
    decisions = [x for _, x in all_decisions()]
    cards = plot_records()
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
    return build(candidates, decisions, cards, moves, drafts, revisions,
                 plot_review_overview(plot_findings), prose_review_overview(prose_findings))


def main():
    p = argparse.ArgumentParser(description="Read-only project status dashboard")
    p.parse_args()
    try:
        print(json.dumps(collect(), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
