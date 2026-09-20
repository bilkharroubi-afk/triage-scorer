"""
triage-scorer
-------------
Turns a flat list of items pulled from several sources (inbox, task list,
calendar, whatever feeds you have) into a ranked, bucketed daily brief —
instead of the chronological dump most tools give you by default.

Why this exists
----------------
Pulling items from multiple sources and sorting them by date is the easy
part. The useful part is deciding what actually deserves your attention
first, and "most recent" is a bad proxy for that: a low-stakes item from
five minutes ago will out-rank a real deadline from yesterday if you just
sort by timestamp.

This script scores each item on three independent signals and combines
them into one number:

1. Keyword weight — a configurable dictionary maps terms to a weight
   (e.g. "urgent": 8, "fyi": -2). Every match in the item's text
   contributes its weight, case-insensitively. This is the cheapest and
   most reliable signal available without calling out to any model.

2. Deadline pressure — if an item carries a "due" date, its score rises
   as the date approaches and spikes further once it's overdue, rather
   than rising linearly to infinity or dropping off a cliff at zero.

3. Recency — a small, capped bonus for items that are genuinely new,
   so two equally-scored items don't tie forever and stale-but-important
   items don't get buried by noise.

The three signals are summed, then the list is split into buckets
(urgent / soon / later) using configurable thresholds, so the output
reads as a triaged brief rather than a raw ranked list.

Usage
-----
    python triage_scorer.py example_items.json config.json

Input format (see example_items.json):
    [
      {
        "id": "item-1",
        "source": "inbox",
        "text": "Please review the contract before Friday, it's urgent.",
        "timestamp": "2026-09-19T08:00:00",
        "due": "2026-09-22"
      },
      ...
    ]

`due` and `timestamp` are optional. Items without a `due` date simply get
no deadline-pressure contribution.

Config format (see config.json):
    {
      "keywords": {"urgent": 8, "asap": 6, "fyi": -2, "newsletter": -5},
      "deadline_weight": 3.0,
      "deadline_horizon_days": 7,
      "recency_half_life_hours": 24,
      "recency_max_bonus": 4,
      "bucket_thresholds": {"urgent": 8, "soon": 3}
    }
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path


@dataclass
class ScoredItem:
    item: dict
    keyword_score: float
    deadline_score: float
    recency_score: float

    @property
    def total(self) -> float:
        return self.keyword_score + self.deadline_score + self.recency_score


def score_keywords(text: str, keywords: dict) -> float:
    lowered = text.lower()
    return sum(weight for term, weight in keywords.items() if term.lower() in lowered)


def score_deadline(due_str: str | None, horizon_days: float, weight: float, today: date) -> float:
    if not due_str:
        return 0.0
    due = datetime.fromisoformat(due_str).date()
    days_left = (due - today).days
    if days_left < 0:
        # Overdue items get the full weight plus a flat penalty-turned-priority bump.
        return weight * horizon_days + abs(days_left) * weight
    if days_left >= horizon_days:
        return 0.0
    # Linear ramp: further out than the horizon contributes nothing,
    # due today contributes the full weight * horizon.
    return weight * (horizon_days - days_left)


def score_recency(timestamp_str: str | None, half_life_hours: float, max_bonus: float, now: datetime) -> float:
    if not timestamp_str:
        return 0.0
    ts = datetime.fromisoformat(timestamp_str)
    age_hours = max((now - ts).total_seconds() / 3600.0, 0.0)
    # Exponential decay capped at max_bonus, halving every half_life_hours.
    decay = 0.5 ** (age_hours / half_life_hours) if half_life_hours > 0 else 0.0
    return max_bonus * decay


def score_items(items: list, config: dict, now: datetime | None = None) -> list:
    now = now or datetime.now()
    today = now.date()

    keywords = config.get("keywords", {})
    deadline_weight = config.get("deadline_weight", 3.0)
    horizon_days = config.get("deadline_horizon_days", 7)
    half_life_hours = config.get("recency_half_life_hours", 24)
    max_bonus = config.get("recency_max_bonus", 4)

    scored = []
    for item in items:
        text = item.get("text", "")
        kw_score = score_keywords(text, keywords)
        dl_score = score_deadline(item.get("due"), horizon_days, deadline_weight, today)
        rc_score = score_recency(item.get("timestamp"), half_life_hours, max_bonus, now)
        scored.append(ScoredItem(item=item, keyword_score=kw_score, deadline_score=dl_score, recency_score=rc_score))

    scored.sort(key=lambda s: s.total, reverse=True)
    return scored


def bucket_items(scored: list, thresholds: dict) -> dict:
    urgent_cut = thresholds.get("urgent", 8)
    soon_cut = thresholds.get("soon", 3)

    buckets = {"urgent": [], "soon": [], "later": []}
    for s in scored:
        if s.total >= urgent_cut:
            buckets["urgent"].append(s)
        elif s.total >= soon_cut:
            buckets["soon"].append(s)
        else:
            buckets["later"].append(s)
    return buckets


def render_markdown(buckets: dict) -> str:
    labels = {"urgent": "Urgent", "soon": "Soon", "later": "Later"}
    lines = ["# Daily brief", ""]
    for key in ("urgent", "soon", "later"):
        entries = buckets[key]
        if not entries:
            continue
        lines.append(f"## {labels[key]}")
        lines.append("")
        for s in entries:
            source = s.item.get("source", "unknown")
            text = s.item.get("text", "")
            lines.append(f"- **[{source}]** {text}  _(score: {s.total:.1f})_")
        lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: python triage_scorer.py <items.json> <config.json>")
        sys.exit(1)

    items_path, config_path = sys.argv[1], sys.argv[2]
    items = json.loads(Path(items_path).read_text(encoding="utf-8"))
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    scored = score_items(items, config)
    buckets = bucket_items(scored, config.get("bucket_thresholds", {}))
    print(render_markdown(buckets))


if __name__ == "__main__":
    main()
