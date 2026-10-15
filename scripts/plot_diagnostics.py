#!/usr/bin/env python3
"""Read-only structural plot diagnostics; findings are not literary verdicts."""
import argparse
import json
import sys
from plot_cards import records as card_records
from plot_moves import records as move_records, effective as effective_cards
from scene_links import records as link_records
from foreshadowing import records as thread_records
from foreshadowing_changes import records as change_records, effective as effective_threads


def diagnose(cards, links, threads):
    approved = {x["plot_id"]: x for x in cards if x["status"] == "approved"}
    findings = []
    def add(code, subject, detail):
        findings.append({"code": code, "subject_id": subject, "detail": detail,
                         "requires_user_review": True, "auto_fix": False,
                         "literary_contradiction_proven": False})
    for x in approved.values():
        if x["kind"] == "scene" and (x["parent_chapter_id"] is None or x["position"] is None):
            add("SCENE_UNPLACED", x["plot_id"], "Scene has no complete chapter/position assignment")
        if x["kind"] == "chapter" and x["position"] is None:
            add("CHAPTER_UNPLACED", x["plot_id"], "Chapter position is not assigned")
    for thread in threads:
        if thread["status"] != "approved":
            continue
        if thread["setup_scene_id"] is None:
            add("SETUP_UNASSIGNED", thread["thread_id"], "Setup scene has not been specified")
        if thread["payoff_scene_id"] is None:
            add("PAYOFF_UNASSIGNED", thread["thread_id"], "Payoff scene has not been specified; this may be intentional")
    # Only explicit 'precedes' asserts temporal precedence. Causal and thematic links do not.
    edges = [(x["from_scene_id"], x["to_scene_id"], x["link_id"])
             for x in links if x["status"] == "approved" and x["relation_type"] == "precedes"]
    graph = {}
    for a, b, lid in edges:
        graph.setdefault(a, set()).add(b)
        ca, cb = approved.get(a), approved.get(b)
        if ca is None or cb is None:
            add("UNKNOWN_SCENE", lid, "Approved precedence references unavailable scene")
            continue
        pa, pb = ca["parent_chapter_id"], cb["parent_chapter_id"]
        if pa is None or pb is None or ca["position"] is None or cb["position"] is None:
            continue
        if pa == pb and ca["position"] >= cb["position"]:
            add("PRECEDENCE_POSITION_CONFLICT", lid, "Explicit precedence disagrees with positions within a chapter")
        elif pa != pb:
            cha, chb = approved.get(pa), approved.get(pb)
            if cha and chb and cha["position"] is not None and chb["position"] is not None and cha["position"] >= chb["position"]:
                add("PRECEDENCE_CHAPTER_CONFLICT", lid, "Explicit precedence disagrees with chapter order")
    visited, active = set(), set()
    cycle_nodes = set()
    def walk(node):
        visited.add(node)
        active.add(node)
        for neighbor in graph.get(node, ()):
            if neighbor in active:
                cycle_nodes.add(neighbor)
            elif neighbor not in visited:
                walk(neighbor)
        active.remove(node)
    for node in sorted(graph):
        if node not in visited:
            walk(node)
    for node in sorted(cycle_nodes):
        add("PRECEDENCE_CYCLE", node, "Explicit precedence graph contains a cycle")
    return {"findings": sorted(findings, key=lambda x: (x["code"], x["subject_id"])),
            "count": len(findings), "user_review_required": True,
            "inferred_causality": False, "canon_modified": False}


def main():
    p = argparse.ArgumentParser(description="Structural review findings for approved plot")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()
    try:
        cards = card_records()
        moves = move_records(cards)
        effective = effective_cards(cards, moves)
        links = link_records(cards)
        threads = thread_records(cards)
        scenes = {x["plot_id"] for x in cards if x["kind"] == "scene" and x["status"] == "approved"}
        changes = change_records(threads, scenes)
        result = diagnose(effective, links, effective_threads(threads, changes, scenes))
        if args.summary:
            result = {"count": result["count"], "by_code": {
                code: sum(x["code"] == code for x in result["findings"])
                for code in sorted({x["code"] for x in result["findings"]})}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
