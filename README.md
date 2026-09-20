# triage-scorer

A small, dependency-free Python tool that turns a flat list of items pulled from several sources (inbox, task list, calendar, whatever feeds you have) into a ranked, bucketed daily brief — instead of the chronological dump most tools give you by default.

## The problem

Pulling items from multiple sources and sorting them by date is the easy part. The useful part is deciding what actually deserves your attention first, and "most recent" is a bad proxy for that: a low-stakes item from five minutes ago will out-rank a real deadline from yesterday if you just sort by timestamp.

I built this after noticing that every "daily digest" script I wrote for myself had the same flaw — it looked organized but it wasn't actually prioritized. Sorting isn't triage.

## The approach

Each item gets scored on three independent signals, combined into one number:

1. **Keyword weight.** A configurable dictionary maps terms to a weight (`"urgent": 8`, `"fyi": -2`, ...). Every match in the item's text contributes its weight, case-insensitively. It's the cheapest and most reliable signal you can get without calling out to a model.

2. **Deadline pressure.** If an item carries a `due` date, its score rises as the date approaches and keeps rising once it's overdue, rather than climbing to infinity or dropping off a cliff at zero.

3. **Recency.** A small, capped, exponentially-decaying bonus so two equally-scored items don't tie forever and stale-but-important items don't get buried by noise.

The three signals are summed, then the list is split into buckets (`urgent` / `soon` / `later`) using configurable thresholds, so the output reads as a triaged brief rather than a raw ranked list.

## Usage

```bash
python triage_scorer.py example_items.json config.json
```

Input format (`example_items.json`):

```json
[
  {
    "id": "item-1",
    "source": "inbox",
    "text": "Please review the contract before Friday, it's urgent.",
    "timestamp": "2026-09-19T08:00:00",
    "due": "2026-09-22"
  }
]
```

`due` and `timestamp` are both optional — an item with neither just falls back to its keyword score.

Config format (`config.json`):

```json
{
  "keywords": {"urgent": 8, "asap": 6, "fyi": -2, "newsletter": -5},
  "deadline_weight": 3.0,
  "deadline_horizon_days": 7,
  "recency_half_life_hours": 24,
  "recency_max_bonus": 4,
  "bucket_thresholds": {"urgent": 8, "soon": 3}
}
```

Tune the keyword dictionary and thresholds to whatever vocabulary actually shows up in your own sources — the scoring logic doesn't care where the text came from.

## Why this is here

I'm not a developer by trade — B2B SaaS sales background — but I run several small automations day to day, including one that pulls from multiple sources every morning and needs to decide what actually matters first. This is a generic, from-scratch reimplementation of that scoring pattern: no real data, no source-specific code, just the ranking logic that makes the difference between a sorted list and an actual triage.

## License

MIT — see [LICENSE](LICENSE).
