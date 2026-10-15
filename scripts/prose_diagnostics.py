#!/usr/bin/env python3
"""Read-only structural checks for approved prose and approved plot placement.

No semantic claims about character behavior, continuity, or literary quality.
"""
import argparse
import json
import sys
from plot_cards import records as card_records, overview as card_overview
from plot_moves import records as move_records, effective as effective_cards
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records, effective as effective_prose


def diagnose(cards, moves, drafts, revisions):
    plot = card_overview(effective_cards(cards, moves))
    prose = {x["scene_id"]: x for x in effective_prose(drafts, revisions)}
    findings = []

    def add(code, subject, detail):
        findings.append({"code": code, "subject_id": subject, "detail": detail,
                         "requires_user_review": True, "auto_fix": False,
                         "literary_contradiction_proven": False})

    chapter_positions = {}
    for chapter in plot["ordered_chapters"]:
        chapter_positions.setdefault(chapter["position"], []).append(chapter["plot_id"])
        scene_positions = {}
        for scene in chapter["scenes"]:
            sid = scene["plot_id"]
            scene_positions.setdefault(scene["position"], []).append(sid)
            if sid not in prose:
                add("APPROVED_SCENE_WITHOUT_PROSE", sid, "Ordered scene has no approved prose")
        for pos, ids in scene_positions.items():
            if len(ids) > 1:
                for sid in ids:
                    add("DUPLICATE_SCENE_POSITION", sid, "Several scenes share the same chapter position")
    for pos, ids in chapter_positions.items():
        if len(ids) > 1:
            for cid in ids:
                add("DUPLICATE_CHAPTER_POSITION", cid, "Several chapters share the same position")

    for scene in plot["unplaced_scenes"]:
        add("SCENE_UNPLACED", scene["plot_id"], "Approved scene has no complete chapter/position assignment")
    for chapter in plot["unplaced_chapters"]:
        add("CHAPTER_UNPLACED", chapter["plot_id"], "Approved chapter has no position")

    placed = {scene["plot_id"] for chapter in plot["ordered_chapters"] for scene in chapter["scenes"]}
    for sid in sorted(prose):
        if sid not in placed:
            add("APPROVED_PROSE_NOT_IN_MANUSCRIPT", sid, "Approved prose is excluded from ordered manuscript")
    for draft in drafts:
        if draft["status"] == "proposed":
            add("PENDING_PROSE_DRAFT", draft["draft_id"], "Unapproved prose draft exists")
    for revision in revisions:
        if revision["status"] == "proposed":
            add("PENDING_PROSE_REVISION", revision["revision_id"], "Unapproved prose revision exists")

    return {"findings": sorted(findings, key=lambda x: (x["code"], x["subject_id"])),
            "count": len(findings), "semantic_continuity_checked": False,
            "narrative_quality_judged": False, "automatic_corrections": False,
            "source_records_modified": False}


def main():
    p = argparse.ArgumentParser(description="Read-only structural prose checks")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        drafts = draft_records(cards)
        revisions = revision_records(drafts)
        result = diagnose(cards, moves, drafts, revisions)
        if args.summary:
            result = {"count": result["count"], "by_code": {
                code: sum(x["code"] == code for x in result["findings"])
                for code in sorted({x["code"] for x in result["findings"]})},
                "semantic_continuity_checked": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
