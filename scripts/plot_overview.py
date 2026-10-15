#!/usr/bin/env python3
"""Read-only unified plot overview. No inferred sequence, causality or payoff."""
import argparse
import json
import sys

from plot_cards import records as card_records, overview as card_overview
from plot_moves import records as move_records, effective as effective_cards
from scene_links import records as link_records, overview as link_overview
from foreshadowing import records as thread_records, overview as thread_overview
from foreshadowing_changes import records as change_records, effective as effective_threads


def build(cards, moves, links, threads, changes):
    effective_plot = effective_cards(cards, moves)
    scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
    effective_foreshadowing = effective_threads(threads, changes, scenes)
    plot = card_overview(effective_plot)
    relationships = link_overview(links)
    foreshadowing = thread_overview(effective_foreshadowing)
    scene_links_by_id = {}
    for relation_type, items in relationships["approved_by_type"].items():
        for link in items:
            for sid in (link["from_scene_id"], link["to_scene_id"]):
                scene_links_by_id.setdefault(sid, []).append({
                    "link_id": link["link_id"], "relation_type": relation_type,
                    "from_scene_id": link["from_scene_id"], "to_scene_id": link["to_scene_id"]})
    thread_ids_by_scene = {}
    for thread in foreshadowing["approved"]:
        for field, role in (("setup_scene_id", "setup"), ("payoff_scene_id", "payoff")):
            sid = thread[field]
            if sid is not None:
                thread_ids_by_scene.setdefault(sid, []).append({
                    "thread_id": thread["thread_id"], "role": role})
    for chapter in plot["ordered_chapters"]:
        for scene in chapter["scenes"]:
            scene["approved_links"] = sorted(scene_links_by_id.get(scene["plot_id"], []), key=lambda x: x["link_id"])
            scene["foreshadowing"] = sorted(thread_ids_by_scene.get(scene["plot_id"], []), key=lambda x: (x["thread_id"], x["role"]))
    return {
        "plot": plot,
        "scene_relationships": relationships,
        "foreshadowing": foreshadowing,
        "unplaced_scene_ids": [x["plot_id"] for x in plot["unplaced_scenes"]],
        "unassigned_payoff_thread_ids": foreshadowing["without_payoff"],
        "unassigned_setup_thread_ids": foreshadowing["without_setup"],
        "inferred_story_order": False,
        "inferred_causality": False,
        "unassigned_payoff_is_error": False,
        "source_records_modified": False,
    }


def main():
    p = argparse.ArgumentParser(description="Integrated approved plot, scene links and foreshadowing")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        links = link_records(cards)
        threads = thread_records(cards)
        scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
        changes = change_records(threads, scenes)
        result = build(cards, moves, links, threads, changes)
        if args.summary:
            result = {"ordered_chapters": len(result["plot"]["ordered_chapters"]),
                      "unplaced_scenes": len(result["unplaced_scene_ids"]),
                      "approved_scene_links": sum(len(x) for x in result["scene_relationships"]["approved_by_type"].values()),
                      "approved_foreshadowing": len(result["foreshadowing"]["approved"]),
                      "unassigned_payoffs": len(result["unassigned_payoff_thread_ids"]),
                      "source_records_modified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
