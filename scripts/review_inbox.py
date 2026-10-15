#!/usr/bin/env python3
"""Read-only action inbox across candidate, plot and prose review workflows."""
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


def build(candidates, decisions, cards, drafts, revisions, plot_review, prose_review):
    items = []
    decided = {x["candidate_id"] for x in decisions}
    for x in candidates:
        if x["candidate_id"] not in decided:
            items.append({"category": "canon_candidate", "id": x["candidate_id"],
                          "action": "approve_or_reject", "status": "pending"})
    for x in cards:
        if x["status"] == "proposed":
            items.append({"category": "plot_card", "id": x["plot_id"],
                          "action": "approve_or_reject", "status": "pending"})
    for x in drafts:
        if x["status"] == "proposed":
            items.append({"category": "prose_draft", "id": x["draft_id"],
                          "action": "approve_or_reject", "status": "pending"})
    for x in revisions:
        if x["status"] == "proposed":
            items.append({"category": "prose_revision", "id": x["revision_id"],
                          "action": "approve_or_reject", "status": "pending"})
    for category, report in (("plot_diagnostic", plot_review), ("prose_diagnostic", prose_review)):
        for f in report["findings"]:
            if f["review"] == "unreviewed":
                items.append({"category": category, "id": f["subject_id"],
                              "code": f["code"], "finding_sha256": f["finding_sha256"],
                              "action": "review_finding", "status": "pending"})
            elif f["review"] == "needs_revision":
                items.append({"category": category, "id": f["subject_id"],
                              "code": f["code"], "finding_sha256": f["finding_sha256"],
                              "action": "consider_revision", "status": "needs_revision"})
    items.sort(key=lambda x: (x["category"], x["id"], x.get("code", "")))
    counts = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"total": len(items), "by_category": counts, "items": items,
            "user_decision_required": True, "automatic_approval": False,
            "automatic_changes": False}


def main():
    p = argparse.ArgumentParser(description="Unified pending review and action inbox")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
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
        result = build(candidates, decisions, cards, drafts, revisions,
                       plot_review_overview(plot_findings), prose_review_overview(prose_findings))
        print(json.dumps({"total": result["total"], "by_category": result["by_category"]}
                         if args.summary else result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
