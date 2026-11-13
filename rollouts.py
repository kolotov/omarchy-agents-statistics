"""Incremental reader for local Codex JSONL rollouts.

Only metadata, typed-prompt events, usage counters and completed turn times
are retained. The supported record shapes mirror Omarchy's native reader.
"""
from contextlib import contextmanager
from compression import zstd
from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import math

MAX_LINE_BYTES = 64 * 1024 * 1024
MARKERS = (b'"session_meta"', b'"turn_context"', b'"thread_settings_applied"',
           b'"user_message"', b'"UserMessage"', b'"token_count"',
           b'"token_usage_record"', b'"task_complete"', b'"turn_aborted"')
USAGE_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                "output_tokens", "reasoning_output_tokens", "total_tokens")
READ_ERRORS = (OSError, ValueError, EOFError, zstd.ZstdError)


def timestamp(value):
    if type(value) in (int, float):
        return float(value) if math.isfinite(value) and 0 < value < 32503680000 else None
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def local_day(value):
    value = timestamp(value)
    if value is None:
        return None
    try:
        day = datetime.fromtimestamp(value).date()
        return day.isoformat() if date(2022, 1, 1) <= day <= date.today() else None
    except (ValueError, OverflowError, OSError):
        return None


def count(value):
    return value if type(value) is int and 0 <= value <= 10**15 else 0


def obj(value):
    return value if isinstance(value, dict) else {}


@contextmanager
def open_rollout(path):
    if path.name.endswith(".zst"):
        with zstd.open(path, "rb") as stream:
            yield stream
    else:
        with path.open("rb") as stream:
            yield stream


def fingerprint(stream, offset):
    digest = hashlib.sha256()
    for position, length in ((0, min(offset, 4096)), (max(0, offset - 4096), min(offset, 4096))):
        stream.seek(position)
        digest.update(stream.read(length))
    return digest.hexdigest()


def fresh_record(path, info):
    return {"mtime": info.st_mtime_ns, "size": info.st_size,
            "file": [info.st_dev, info.st_ino], "offset": 0,
            "session": str(path), "seenMeta": False, "typed": True,
            "provider": "", "model": "codex", "days": {}, "intervals": [],
            "pending": [], "records": False, "responses": [], "total": None,
            "complete": True}


def valid_record(record):
    """Reject damaged derived state so it can be rebuilt from the transcript."""
    if not isinstance(record, dict):
        return False
    if any(type(record.get(key)) is not int or record[key] < 0
           for key in ("mtime", "size", "offset")):
        return False
    if any(type(record.get(key)) is not bool
           for key in ("seenMeta", "typed", "records", "complete")):
        return False
    identity = record.get("file")
    if not isinstance(identity, list) or len(identity) != 2 or any(type(n) is not int or n < 0 for n in identity):
        return False
    if record.get("session") is not None and not isinstance(record.get("session"), str):
        return False
    if any(not isinstance(record.get(key), str) for key in ("provider", "model")):
        return False
    responses = record.get("responses")
    if not isinstance(responses, list) or any(not isinstance(key, str) or len(key) != 64 for key in responses):
        return False
    total = record.get("total")
    if total is not None and (not isinstance(total, dict) or any(type(n) is not int or n < 0 for n in total.values())):
        return False
    pending, days, intervals = record.get("pending"), record.get("days"), record.get("intervals")
    if not isinstance(pending, list) or not isinstance(days, dict) or not isinstance(intervals, list):
        return False
    try:
        for day in pending:
            date.fromisoformat(day)
        for day, models in days.items():
            date.fromisoformat(day)
            if not isinstance(models, dict):
                return False
            for model, values in models.items():
                if (not isinstance(model, str) or not isinstance(values, list) or len(values) != 5
                        or any(type(n) is not int or n < 0 for n in values)):
                    return False
        for interval in intervals:
            if (not isinstance(interval, list) or len(interval) != 2
                    or any(type(n) not in (int, float) for n in interval)
                    or not 0 < interval[0] < interval[1] < 32503680000):
                return False
    except (ValueError, TypeError):
        return False
    return True


def consume(record, entry, responses):
    kind = entry.get("type")
    payload = obj(entry.get("payload"))
    if kind == "session_meta":
        if record["seenMeta"]:
            return
        record["seenMeta"] = True
        source = payload.get("source")
        record["typed"] = not (isinstance(source, dict) and ("subagent" in source or "internal" in source))
        thread = payload.get("id")
        record["session"] = str(thread or record["session"]) if record["typed"] else str(payload.get("session_id") or payload.get("parent_thread_id") or "") or None
        record["provider"] = str(payload.get("model_provider") or "")[:256]
        return
    if kind == "turn_context":
        record["model"] = str(payload.get("model") or payload.get("model_slug") or record["model"])[:256]
        return
    if kind == "event_msg":
        event = payload.get("type")
        if event == "thread_settings_applied":
            settings = obj(payload.get("thread_settings"))
            model = settings.get("model") or obj(obj(settings.get("collaboration_mode")).get("settings")).get("model")
            if model:
                record["model"] = str(model)[:256]
            return
        typed_prompt = ((event == "user_message" and payload.get("kind") in (None, "plain")) or
                        (event == "item_completed" and obj(payload.get("item")).get("type") == "UserMessage"))
        if typed_prompt:
            day = local_day(entry.get("timestamp"))
            if record["typed"] and day:
                record["pending"].append(day)
            return
        if event in ("task_complete", "turn_aborted") and record["typed"]:
            start = timestamp(payload.get("started_at"))
            end = timestamp(payload.get("completed_at") or entry.get("timestamp"))
            if start is not None and end is not None and 0 < end - start < 31 * 86400:
                record["intervals"].append([start, end])
            return
    if kind == "token_usage_record":
        record["records"] = True
        cumulative = obj(payload.get("thread_token_usage"))
        identity = hashlib.sha256(json.dumps([str(payload.get("response_id") or "")[:512], *[count(cumulative.get(k)) for k in USAGE_FIELDS]]).encode()).hexdigest()
        if identity in responses:
            return
        responses.add(identity)
        record["responses"].append(identity)
        usage = obj(payload.get("usage"))
    else:
        if kind == "response_item":
            payload = obj(payload.get("payload")) or payload
        if payload.get("type") != "token_count" or record["records"]:
            return
        info = obj(payload.get("info"))
        cumulative = obj(info.get("total_token_usage"))
        if cumulative and cumulative == record["total"]:
            return
        record["total"] = cumulative or None
        usage = obj(info.get("last_token_usage"))
    cached = count(usage.get("cached_input_tokens"))
    written = count(usage.get("cache_write_input_tokens"))
    values = [max(0, count(usage.get("input_tokens")) - cached - written),
              count(usage.get("output_tokens")), cached, written]
    day = local_day(entry.get("timestamp"))
    if not day or not any(values):
        return
    bucket = record["days"].setdefault(day, {}).setdefault(record["model"], [0, 0, 0, 0, 0])
    for index, value in enumerate(values):
        bucket[index] += value
    for prompt_day in record["pending"]:
        record["days"].setdefault(prompt_day, {}).setdefault(record["model"], [0, 0, 0, 0, 0])[4] += 1
    record["pending"] = []


def read_rollout(path, info, previous=None):
    record = fresh_record(path, info)
    compressed = path.name.endswith(".zst")
    with open_rollout(path) as stream:
        if (not compressed and valid_record(previous) and previous.get("complete") and
                previous.get("file") == record["file"] and info.st_size >= previous.get("offset", 0) and
                previous.get("fingerprint") == fingerprint(stream, previous.get("offset", 0))):
            record = deepcopy(previous)
            record.update(mtime=info.st_mtime_ns, size=info.st_size)
        stream.seek(record["offset"])
        responses = set(record["responses"])
        while raw := stream.readline(MAX_LINE_BYTES + 1):
            if len(raw) > MAX_LINE_BYTES:
                record["complete"] = False
                while raw and not raw.endswith(b"\n"):
                    raw = stream.readline(MAX_LINE_BYTES + 1)
                record["offset"] = stream.tell()
                continue
            if not raw.endswith(b"\n"):
                # Leave a partially written final line for the next refresh.
                break
            record["offset"] = stream.tell()
            if not any(marker in raw for marker in MARKERS):
                continue
            try:
                entry = json.loads(raw)
                if isinstance(entry, dict):
                    consume(record, entry, responses)
            except (ValueError, TypeError, RecursionError):
                record["complete"] = False
        if not compressed:
            record["fingerprint"] = fingerprint(stream, record["offset"])
    return record


def with_pending_prompts(record):
    """An unanswered prompt is visible without mutating incremental state."""
    result = deepcopy(record)
    for day in result["pending"]:
        result["days"].setdefault(day, {}).setdefault(result["model"], [0, 0, 0, 0, 0])[4] += 1
    return result
