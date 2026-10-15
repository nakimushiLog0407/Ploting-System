#!/usr/bin/env python3
"""Read-only scene writing context with approved provenance and bounded prior prose."""
import argparse
import json
import sys
from canon_catalog import build_catalog
from canon_revision import load as canon_revisions
from plot_cards import records as card_records, overview as card_overview
from plot_moves import records as move_records, effective as effective_cards
from prose_drafts import records as draft_records
from prose_revisions import records as revision_records, effective as effective_prose


def build(scene_id, cards, moves, drafts, revisions, canon, canon_changes,
          previous_scenes=2, max_prose_chars=6000):
    if not isinstance(previous_scenes, int) or not 0 <= previous_scenes <= 20:
        raise ValueError("previous_scenes must be between 0 and 20")
    if not isinstance(max_prose_chars, int) or not 0 <= max_prose_chars <= 100000:
        raise ValueError("max_prose_chars must be between 0 and 100000")
    effective = effective_cards(cards, moves)
    scenes = {x["plot_id"]: x for x in effective if x["kind"] == "scene" and x["status"] == "approved"}
    if scene_id not in scenes:
        raise ValueError("Target must be an approved scene")
    plot = card_overview(effective)
    ordered = [(chapter, scene) for chapter in plot["ordered_chapters"] for scene in chapter["scenes"]]
    indices = [i for i, (_, scene) in enumerate(ordered) if scene["plot_id"] == scene_id]
    if len(indices) > 1:
        raise ValueError("Scene appears multiple times in ordered plot")
    text_by_scene = {x["scene_id"]: x for x in effective_prose(drafts, revisions)}
    prior = []
    if indices:
        for chapter, scene in ordered[max(0, indices[0] - previous_scenes):indices[0]]:
            entry = text_by_scene.get(scene["plot_id"])
            if entry is None:
                prior.append({"scene_id": scene["plot_id"], "chapter_id": chapter["plot_id"],
                              "approved_prose": None, "reason": "No approved prose"})
            else:
                text = entry["text"]
                prior.append({"scene_id": scene["plot_id"], "chapter_id": chapter["plot_id"],
                              "draft_id": entry["draft_id"], "approved_prose": text[-max_prose_chars:] if max_prose_chars else "",
                              "truncated": len(text) > max_prose_chars})
    current, history = canon_revisions(canon) if canon_changes is None else canon_changes
    approved_canon = [{**x, "content": current[x["candidate_id"]],
                       "original_content": x["content"],
                       "revised": current[x["candidate_id"]] != x["content"]}
                      for x in canon]
    target = scenes[scene_id]
    return {"target_scene": target, "target_position_confirmed": bool(indices),
            "preceding_approved_prose": prior,
            "approved_canon": approved_canon,
            "canon_revision_history": [x["revision_id"] for x in history if x["status"] == "approved"],
            "target_existing_approved_prose": text_by_scene.get(scene_id),
            "unapproved_drafts_excluded": True,
            "unapproved_canon_excluded": True,
            "context_is_reference_not_new_canon": True,
            "automatic_writing": False,
            "source_records_modified": False}


def main():
    p = argparse.ArgumentParser(description="Assemble approved context for a target scene")
    p.add_argument("--scene-id", required=True)
    p.add_argument("--previous-scenes", type=int, default=2)
    p.add_argument("--max-prose-chars", type=int, default=6000)
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        drafts = draft_records(cards)
        revisions = revision_records(drafts)
        canon = build_catalog()
        result = build(args.scene_id, cards, moves, drafts, revisions, canon, None,
                       args.previous_scenes, args.max_prose_chars)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
