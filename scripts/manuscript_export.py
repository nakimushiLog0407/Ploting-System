#!/usr/bin/env python3
"""Read-only manuscript assembly from explicitly ordered, approved prose."""
import argparse
import json
import sys
from pathlib import Path
from plot_cards import records as card_records, overview as card_overview
from plot_moves import records as move_records, effective as effective_cards
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records, effective as effective_prose


def assemble(cards, moves, drafts, revisions):
    plot = card_overview(effective_cards(cards, moves))
    texts = {x["scene_id"]: x for x in effective_prose(drafts, revisions)}
    chapters, missing, included = [], [], set()
    for chapter in plot["ordered_chapters"]:
        scenes = []
        for scene in chapter["scenes"]:
            sid = scene["plot_id"]
            if sid in texts:
                entry = texts[sid]
                scenes.append({"scene_id": sid, "draft_id": entry["draft_id"],
                               "approved_revision_ids": entry["approved_revision_ids"],
                               "text": entry["text"]})
                included.add(sid)
            else:
                missing.append({"scene_id": sid, "chapter_id": chapter["plot_id"],
                                "reason": "No approved prose"})
        chapters.append({"chapter_id": chapter["plot_id"], "title": chapter["title"],
                         "position": chapter["position"], "scenes": scenes})
    excluded = [{"scene_id": sid, "draft_id": entry["draft_id"],
                 "reason": "Scene not in explicitly ordered chapters"}
                for sid, entry in texts.items() if sid not in included]
    return {"chapters": chapters, "missing_approved_prose": missing,
            "excluded_approved_prose": excluded,
            "unplaced_scene_ids": [x["plot_id"] for x in plot["unplaced_scenes"]],
            "unplaced_chapter_ids": [x["plot_id"] for x in plot["unplaced_chapters"]],
            "pending_draft_ids": [x["draft_id"] for x in drafts if x["status"] == "proposed"],
            "automatic_fill": False, "inferred_order": False, "source_records_modified": False}


def render_text(manuscript):
    chunks = []
    for chapter in manuscript["chapters"]:
        chunks.append(chapter["title"])
        for scene in chapter["scenes"]:
            chunks.append(scene["text"])
    return "\n\n".join(chunks) + ("\n" if chunks else "")


def main():
    p = argparse.ArgumentParser(description="Export explicitly approved manuscript")
    p.add_argument("--format", choices=("json", "text"), default="json")
    p.add_argument("--output")
    p.add_argument("--require-complete", action="store_true")
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        drafts = draft_records(cards)
        revisions = revision_records(drafts)
        result = assemble(cards, moves, drafts, revisions)
        if args.require_complete and (result["missing_approved_prose"] or result["excluded_approved_prose"]
                                      or result["unplaced_scene_ids"] or result["unplaced_chapter_ids"]):
            raise ValueError("Manuscript incomplete; inspect JSON report")
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_text(result)
        if args.output:
            destination = Path(args.output).resolve()
            if destination.is_relative_to(Path(__file__).resolve().parents[1]):
                raise ValueError("Export must be outside repository")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            print(json.dumps({"output": str(destination), "format": args.format}, ensure_ascii=False))
        else:
            print(content, end="")
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
