#!/usr/bin/env python3
"""Local Codex activity across account homes; never reads credentials or sends data."""
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import tempfile

from rollouts import READ_ERRORS, read_rollout, valid_record, with_pending_prompts

SCHEMA = 3
MAX_JSON = 64 * 1024 * 1024


def load(path, limit=MAX_JSON):
    try:
        if path.stat().st_size <= limit:
            value = json.loads(path.read_text())
            return value if isinstance(value, dict) else {}
    except (OSError, ValueError, RecursionError):
        pass
    return {}


def discover_homes(home, state):
    registry = load(state / "omarchy/agents/accounts/codex.json", 1024 * 1024)
    homes = [home / ".codex"]
    if os.environ.get("CODEX_HOME"):
        homes.append(Path(os.environ["CODEX_HOME"]).expanduser())
    accounts = registry.get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    for account in accounts:
        if isinstance(account, dict) and isinstance(account.get("home"), str) and account["home"]:
            homes.append(Path(account["home"]).expanduser())
    return sorted({p.resolve() for p in homes}), len(accounts)


def rollout_files(homes):
    files = {}
    roots = {(home / name).resolve() for home in homes for name in ("sessions", "archived_sessions")}
    for root in sorted(roots):
        for path in root.rglob("*.jsonl*"):
            if not path.name.endswith((".jsonl", ".jsonl.zst")):
                continue
            if path.suffix == ".zst" and path.with_suffix("").exists():
                continue
            info = path.stat()
            files.setdefault((info.st_dev, info.st_ino), path.resolve())
    return list(files.values())


def union_intervals(intervals):
    result = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def summarize(records, today=None):
    today = today or date.today()
    days = defaultdict(lambda: {"tokens": 0, "prompts": 0, "seconds": 0})
    sessions = set()
    intervals = []
    for record in records:
        # Shared account history and physical copies of a rollout count once.
        for key, models in record.get("days", {}).items():
            try:
                day = date.fromisoformat(key)
            except (ValueError, TypeError):
                continue
            if day > today:
                continue
            for counts in models.values():
                days[key]["tokens"] += sum(counts[:4])
                days[key]["prompts"] += counts[4]
                if record.get("session") and any(counts):
                    sessions.add(record["session"])
        intervals.extend(record.get("intervals", []))
    for start, end in union_intervals(intervals):
        while start < end:
            local = datetime.fromtimestamp(start).astimezone()
            next_date = local.date() + timedelta(days=1)
            midnight = datetime.combine(next_date, datetime.min.time()).astimezone().timestamp()
            stop = min(end, midnight)
            if local.date() <= today:
                days[local.date().isoformat()]["seconds"] += stop - start
            start = stop
    active = sorted(date.fromisoformat(key) for key, value in days.items() if value["tokens"] or value["prompts"])
    longest = run = 0
    previous = None
    for day in active:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    current = 0
    cursor = today if today in active else today - timedelta(days=1)
    active_set = set(active)
    while cursor in active_set:
        current += 1
        cursor -= timedelta(days=1)
    return {
        "days": {key: {**value, "seconds": round(value["seconds"])} for key, value in sorted(days.items())},
        "totalTokens": sum(v["tokens"] for v in days.values()),
        "totalPrompts": sum(v["prompts"] for v in days.values()),
        "agentSeconds": round(sum(v["seconds"] for v in days.values())),
        "totalSessions": len(sessions), "activeDays": len(active),
        "currentStreak": current, "longestStreak": longest,
        "peakTokens": max((v["tokens"] for v in days.values()), default=0),
    }


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".statistics-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, separators=(",", ":"))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def collect(cache_path):
    home = Path.home()
    state = Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state")
    homes, accounts = discover_homes(home, state)
    zone = [os.environ.get("TZ"), str(datetime.now().astimezone().tzinfo)]
    cache = load(cache_path)
    expected = [SCHEMA, zone]
    cached = cache.get("files", {}) if cache.get("version") == expected else {}
    if not isinstance(cached, dict):
        cached = {}
    files = {}
    unique = {}
    failures = 0
    for path in rollout_files(homes):
        key = str(path)
        try:
            stat = path.stat()
            old = cached.get(key, {})
            if not valid_record(old):
                old = None
            if old and old["complete"] and old["mtime"] == stat.st_mtime_ns and old["size"] == stat.st_size:
                record = old
            else:
                record = read_rollout(path, stat, old or None)
            files[key] = record
            if not record.get("complete", False):
                failures += 1
            # Same transcript reachable through different account paths or copies.
            # A fork has a different UUID and retains its independent usage.
            identity = path.name.removesuffix(".zst")
            if identity not in unique or record.get("size", 0) > unique[identity].get("size", 0):
                unique[identity] = with_pending_prompts(record)
        except READ_ERRORS:
            failures += 1
    atomic_write(cache_path, {"version": expected, "files": files})
    result = summarize(unique.values())
    result.update({"schemaVersion": 1, "accounts": max(accounts, 1), "files": len(unique),
                   "partialFiles": failures, "updatedAt": datetime.now().astimezone().isoformat()})
    atomic_write(cache_path.with_name("summary.json"), result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "omarchy/agent-statistics/rollouts.json")
    args = parser.parse_args()
    # One worker even if a panel is open on multiple monitors.
    import fcntl
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    with args.cache.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = collect(args.cache)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
