import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import collect_statistics as stats
from rollouts import read_rollout, with_pending_prompts


class StatisticsTests(unittest.TestCase):
    def test_overlap_counts_once_across_accounts_and_parallel_sessions(self):
        start = datetime(2026, 11, 1, 10).astimezone().timestamp()
        records = [
            {"session": "a", "days": {"2026-11-01": {"model": [100, 20, 70, 0, 2]}}, "intervals": [[start, start + 120]]},
            {"session": "b", "days": {"2026-11-01": {"model": [10, 5, 0, 0, 1]}}, "intervals": [[start + 60, start + 180]]},
        ]
        result = stats.summarize(records, date(2026, 11, 2))
        self.assertEqual(result["totalTokens"], 205)
        self.assertEqual(result["agentSeconds"], 180)
        self.assertEqual(result["totalSessions"], 2)
        self.assertEqual(result["totalPrompts"], 3)

    def test_streak_accepts_yesterday_but_not_a_gap(self):
        record = {"session": "a", "days": {d: {"m": [1, 0, 0, 0, 0]} for d in ["2026-11-01", "2026-11-02", "2026-11-04"]}}
        result = stats.summarize([record], date(2026, 11, 5))
        self.assertEqual(result["longestStreak"], 2)
        self.assertEqual(result["currentStreak"], 1)
        self.assertEqual(stats.summarize([record], date(2026, 11, 6))["currentStreak"], 0)

    def test_completed_turns_numeric_timestamps_and_subagent_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            entries = [
                {"type": "session_meta", "payload": {"source": "cli"}},
                {"type": "event_msg", "payload": {"type": "task_complete", "started_at": 1793527660, "completed_at": 1793527665}},
                {"type": "event_msg", "payload": {"type": "task_started", "started_at": 1793527670}},
            ]
            path.write_text("\n".join(map(json.dumps, entries)) + "\n")
            self.assertEqual(read_rollout(path, path.stat())["intervals"], [[1793527660.0, 1793527665.0]])
            entries[0]["payload"]["source"] = {"subagent": {"parent_thread_id": "a"}}
            path.write_text("\n".join(map(json.dumps, entries)) + "\n")
            self.assertEqual(read_rollout(path, path.stat())["intervals"], [])

    def test_midnight_splits_time_between_days(self):
        start = datetime(2026, 11, 1, 23, 59).astimezone().timestamp()
        end = datetime(2026, 11, 2, 0, 1).astimezone().timestamp()
        result = stats.summarize([{"intervals": [[start, end]]}], date(2026, 11, 3))
        self.assertEqual(result["days"]["2026-11-01"]["seconds"], 60)
        self.assertEqual(result["days"]["2026-11-02"]["seconds"], 60)

    def test_shared_symlink_and_hardlink_history_only_discovered_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a/sessions").mkdir(parents=True)
            (root / "b").mkdir()
            (root / "b/sessions").symlink_to(root / "a/sessions")
            path = root / "a/sessions/rollout.jsonl"
            path.write_text("{}\n")
            self.assertEqual(stats.rollout_files([root / "a", root / "b"]), [path])

    def test_native_reader_deduplicates_usage_and_cached_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            usage = {"input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 20, "total_tokens": 120}
            entries = [
                {"type": "session_meta", "payload": {"id": "a", "source": "cli", "model_provider": "openai"}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": "<img src=\"https://example.invalid/tracker\">"}},
                {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": usage, "total_token_usage": usage}}},
                {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": usage, "total_token_usage": usage}}},
            ]
            for entry in entries:
                entry["timestamp"] = "2026-11-01T10:00:00Z"
            path.write_text("\n".join(map(json.dumps, entries)) + "\n")
            record = with_pending_prompts(read_rollout(path, path.stat()))
            result = stats.summarize([record], date(2026, 11, 2))
            self.assertEqual(result["totalTokens"], 120)
            self.assertEqual(result["totalPrompts"], 1)
            self.assertNotIn("tracker", json.dumps(result))

    def test_incremental_read_retries_partial_line_and_retains_pending_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            def event(payload):
                return json.dumps({"timestamp": "2026-11-01T10:00:00Z", "type": "event_msg", "payload": payload}) + "\n"
            path.write_text(event({"type": "user_message", "message": "hello"}))
            first = read_rollout(path, path.stat())
            self.assertEqual(stats.summarize([with_pending_prompts(first)], date(2026, 11, 2))["totalPrompts"], 1)
            next_line = event({"type": "token_count", "info": {"last_token_usage": {"input_tokens": 10, "output_tokens": 5}, "total_token_usage": {"total_tokens": 15}}})
            with path.open("a") as stream:
                stream.write(next_line[:20])
            partial = read_rollout(path, path.stat(), first)
            self.assertEqual(partial["offset"], first["offset"])
            with path.open("a") as stream:
                stream.write(next_line[20:])
            final = with_pending_prompts(read_rollout(path, path.stat(), partial))
            result = stats.summarize([final], date(2026, 11, 2))
            self.assertEqual(result["totalTokens"], 15)
            self.assertEqual(result["totalPrompts"], 1)

    def test_replaced_file_is_reread_instead_of_reusing_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            def event(tokens):
                return json.dumps({"timestamp": "2026-11-01T10:00:00Z", "type": "token_usage_record", "payload": {"response_id": "r", "thread_token_usage": {"total_tokens": tokens}, "usage": {"input_tokens": tokens}}}) + "\n"
            path.write_text(event(999))
            first = read_rollout(path, path.stat())
            path.write_text(event(100))
            result = stats.summarize([with_pending_prompts(read_rollout(path, path.stat(), first))], date(2026, 11, 2))
            self.assertEqual(result["totalTokens"], 100)

    def test_modern_usage_records_suppress_legacy_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            usage = {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 20, "total_tokens": 120}
            entries = [
                {"type": "token_usage_record", "payload": {"response_id": "r", "usage": usage, "thread_token_usage": usage}},
                {"type": "token_usage_record", "payload": {"response_id": "r", "usage": usage, "thread_token_usage": usage}},
                {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": usage, "total_token_usage": usage}}},
            ]
            for entry in entries:
                entry["timestamp"] = "2026-11-01T10:00:00Z"
            path.write_text("\n".join(map(json.dumps, entries)) + "\n")
            result = stats.summarize([with_pending_prompts(read_rollout(path, path.stat()))], date(2026, 11, 2))
            self.assertEqual(result["totalTokens"], 120)

    def test_compressed_rollout_has_same_counts(self):
        from compression import zstd
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl.zst"
            entry = {"timestamp": "2026-11-01T10:00:00Z", "type": "token_usage_record", "payload": {"usage": {"input_tokens": 100, "output_tokens": 20}}}
            with zstd.open(path, "wb") as stream:
                stream.write((json.dumps(entry) + "\n").encode())
            result = stats.summarize([with_pending_prompts(read_rollout(path, path.stat()))], date(2026, 11, 2))
            self.assertEqual(result["totalTokens"], 120)

    def test_combined_cache_reuses_stable_files_and_deduplicates_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            homes = [root / "a", root / "b"]
            entry = {"timestamp": "2026-11-01T10:00:00Z", "type": "token_usage_record", "payload": {"response_id": "one", "usage": {"input_tokens": 100}, "thread_token_usage": {"input_tokens": 100}}}
            for home in homes:
                (home / "sessions").mkdir(parents=True)
                (home / "sessions/rollout-same.jsonl").write_text(json.dumps(entry) + "\n")
            cache = root / "cache/rollouts.json"
            with patch.object(stats, "discover_homes", return_value=(homes, 3)):
                self.assertEqual(stats.collect(cache)["totalTokens"], 100)
                with patch.object(stats, "read_rollout", wraps=read_rollout) as reader:
                    self.assertEqual(stats.collect(cache)["totalTokens"], 100)
                    reader.assert_not_called()
                entry["payload"]["response_id"] = "two"
                entry["payload"]["thread_token_usage"]["input_tokens"] = 200
                with (homes[1] / "sessions/rollout-same.jsonl").open("a") as stream:
                    stream.write(json.dumps(entry) + "\n")
                result = stats.collect(cache)
                self.assertEqual(result["totalTokens"], 200)
                self.assertEqual(result["files"], 1)
                self.assertEqual(json.loads(cache.with_name("summary.json").read_text())["totalTokens"], 200)

    def test_damaged_cache_rebuilds_without_losing_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sessions").mkdir()
            entry = {"timestamp": "2026-11-01T10:00:00Z", "type": "token_usage_record", "payload": {"usage": {"input_tokens": 100}}}
            (root / "sessions/rollout.jsonl").write_text(json.dumps(entry) + "\n")
            cache = root / "cache/rollouts.json"
            with patch.object(stats, "discover_homes", return_value=([root], 1)):
                stats.collect(cache)
                original = json.loads(cache.read_text())
                damaged = json.loads(json.dumps(original))
                damaged["files"] = []
                cache.write_text(json.dumps(damaged))
                self.assertEqual(stats.collect(cache)["totalTokens"], 100)
                for value in (None, [], {"complete": True}, {**next(iter(original["files"].values())), "days": {"bad-date": []}}):
                    with self.subTest(value=value):
                        damaged = json.loads(json.dumps(original))
                        key = next(iter(damaged["files"]))
                        damaged["files"][key] = value
                        cache.write_text(json.dumps(damaged))
                        result = stats.collect(cache)
                        self.assertEqual(result["totalTokens"], 100)
                        self.assertEqual(result["partialFiles"], 0)


if __name__ == "__main__":
    unittest.main()
