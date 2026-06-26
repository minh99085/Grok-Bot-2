"""Canonical market graph for dependency discovery (AI-2 Step 4).

Nodes are open pulse windows; edges are deterministic structural links (nested 5m inside 15m,
time-family clusters). Grok proposals are attached as advisory edges and must pass LCMM validation
before any trade. PAPER ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.pulse.dependency_arb import group_nested_windows


@dataclass
class GraphNode:
    event_id: str
    series_label: str
    window_seconds: int
    open_ts: float
    close_ts: float
    slug: str = ""
    asset: str = "btc"


@dataclass
class GraphEdge:
    edge_type: str
    parent_id: str
    child_ids: list
    source: str = "deterministic"
    validated: bool = True
    note: str = ""


class MarketGraph:
    """In-memory graph built from the current open window set."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.grok_proposals: list[dict] = []

    def build_from_windows(self, windows: list) -> "MarketGraph":
        self.nodes.clear()
        self.edges.clear()
        for w in windows or []:
            eid = str(getattr(w, "event_id", "") or "")
            if not eid:
                continue
            slug = str(getattr(w, "slug", "") or "")
            asset = "eth" if "eth" in slug.lower() else "btc"
            self.nodes[eid] = GraphNode(
                event_id=eid,
                series_label=str(getattr(w, "series_label", "") or ""),
                window_seconds=int(getattr(w, "window_seconds", 0) or 0),
                open_ts=float(getattr(w, "open_ts", 0) or 0),
                close_ts=float(getattr(w, "close_ts", 0) or 0),
                slug=slug,
                asset=asset,
            )
        for parent, children in group_nested_windows(list(windows or [])):
            self.edges.append(GraphEdge(
                edge_type="nested_implication",
                parent_id=str(parent.event_id),
                child_ids=[str(c.event_id) for c in children],
                source="deterministic",
                validated=True,
                note="P(up_parent) >= max P(up_child) on overlapping windows",
            ))
        # Cross-asset candidate clusters (BTC 5m/15m paired with ETH 5m/15m at same open bucket).
        btc = [n for n in self.nodes.values() if n.asset == "btc"]
        eth = [n for n in self.nodes.values() if n.asset == "eth"]
        for b in btc:
            for e in eth:
                if (b.window_seconds == e.window_seconds
                        and abs(b.open_ts - e.open_ts) < 120.0):
                    self.edges.append(GraphEdge(
                        edge_type="cross_asset_correlated",
                        parent_id=b.event_id,
                        child_ids=[e.event_id],
                        source="deterministic",
                        validated=False,
                        note="advisory cluster — no auto-trade without LCMM template",
                    ))
        return self

    def add_grok_proposals(self, proposals: list[dict]) -> int:
        """Attach LLM proposals as unvalidated edges (report-only until LCMM passes)."""
        n = 0
        for p in proposals or []:
            pid = str(p.get("parent_window_key") or p.get("parent_id") or "")
            cids = list(p.get("child_window_keys") or p.get("child_ids") or [])
            ctype = str(p.get("constraint_type") or "grok_proposal")
            if not pid or not cids:
                continue
            self.edges.append(GraphEdge(
                edge_type=ctype,
                parent_id=pid,
                child_ids=[str(c) for c in cids],
                source="grok",
                validated=False,
                note=str(p.get("description") or "grok_advisory"),
            ))
            n += 1
        self.grok_proposals = list(proposals or [])
        return n

    def nested_pairs(self) -> list[tuple]:
        out = []
        for e in self.edges:
            if e.edge_type == "nested_implication" and e.validated:
                out.append((e.parent_id, e.child_ids))
        return out

    def report(self) -> dict:
        validated = [e for e in self.edges if e.validated]
        rejected = [e for e in self.edges if not e.validated]
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "deterministic_validated_dependencies": len(validated),
            "rejected_or_advisory_dependencies": len(rejected),
            "dependency_proposals": len(self.grok_proposals),
            "edge_types": sorted({e.edge_type for e in self.edges}),
            "nested_pairs": self.nested_pairs()[:20],
            "note": "Graph is rebuilt each tick from open windows; Grok edges are never tradable alone.",
        }