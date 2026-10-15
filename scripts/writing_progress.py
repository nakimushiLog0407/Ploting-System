#!/usr/bin/env python3
"""Read-only writing progress, derived solely from approved plot and prose records."""
import argparse
import json
import sys
from plot_cards import records as card_records, overview as card_overview
from plot_moves import records as move_records, effective as effective_cards
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records, effective as effective_prose

STATUSES = ("not_started", "awaiting_approval", "approved", "revision_pending")


def summarize(cards, moves, drafts, revisions):
    effective = effective_cards(cards, moves)
    plot = card_overview(effective)
    approved_scenes = [x for x in effective if x["kind"] == "scene" and x["status"] == "approved"]
    prose = {x["scene_id"]: x for x in effective_prose(drafts, revisions)}
    pending_drafts = {}
    for draft in drafts:
        if draft["status"] == "proposed":
            pending_drafts.setdefault(draft["scene_id"], []).append(draft["draft_id"])
    pending_revisions = {}
    for rev in revisions:
        if rev["status"] == "proposed":
            pending_revisions.setdefault(rev["draft_id"], []).append(rev["revision_id"])

    def scene_state(scene):
        sid = scene["plot_id"]
        approved = prose.get(sid)
        if approved:
            pending = pending_revisions.get(approved["draft_id"], [])
            state = "revision_pending" if pending else "approved"
        else:
            pending = []
            state = "awaiting_approval" if pending_drafts.get(sid) else "not_started"
        return {"scene_id": sid, "title": scene["title"], "status": state,
                "chapter_id": scene["parent_chapter_id"], "position": scene["position"],
                "approved_draft_id": approved["draft_id"] if approved else None,
                "pending_draft_ids": pending_drafts.get(sid, []),
                "pending_revision_ids": pending}

    all_scenes = [scene_state(x) for x in approved_scenes]
    by_id = {x["scene_id"]: x for x in all_scenes}

    def counts(items):
        return {status: sum(x["status"] == status for x in items) for status in STATUSES}

    chapters = []
    for chapter in plot["ordered_chapters"] + plot["unplaced_chapters"]:
        items = [by_id[x["plot_id"]] for x in approved_scenes
                 if x["parent_chapter_id"] == chapter["plot_id"]]
        chapters.append({"chapter_id": chapter["plot_id"], "title": chapter["title"],
                         "position": chapter["position"], "scenes": items,
                         "counts": counts(items)})
    chapter_ids = {x["chapter_id"] for x in chapters}
    outside = [x for x in all_scenes if x["chapter_id"] not in chapter_ids]
    # A scene assigned to an existing chapter but without a position is still shown
    # inside that chapter, and never silently given a sequence.
    total = counts(all_scenes)
    total["scenes"] = len(all_scenes)
    total["approved_prose_scenes"] = total["approved"] + total["revision_pending"]
    return {"summary": total, "chapters": chapters, "scenes_without_chapter": outside,
            "unplaced_scene_ids": [x["plot_id"] for x in plot["unplaced_scenes"]],
            "unapproved_plot_cards_excluded": True,
            "unapproved_prose_not_counted_as_complete": True,
            "sequence_inferred": False, "source_records_modified": False}


def main():
    p = argparse.ArgumentParser(description="Approved-only scene writing progress")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        cards = card_records()
        drafts = draft_records(cards)
        result = summarize(cards, move_records(cards), drafts, revision_records(drafts))
        print(json.dumps(result["summary"] if args.summary else result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
