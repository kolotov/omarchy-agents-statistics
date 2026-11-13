"""Run the actual QML view offscreen without touching desktop settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta


def demonstration_snapshot():
    today = date(2026, 11, 13)
    days = {}
    for offset in range(365):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5 and day.day % 3:
            continue
        weight = ((offset * 17 + 7) % 19) + 1
        days[day.isoformat()] = {"tokens": weight * 431927, "prompts": weight + 3, "seconds": weight * 317}
    longest = run = 0
    previous = None
    for day in sorted(date.fromisoformat(day) for day in days):
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    current = 0
    while (today - timedelta(days=current)).isoformat() in days:
        current += 1
    return {
        "schemaVersion": 1, "days": days, "accounts": 3,
        "totalTokens": sum(day["tokens"] for day in days.values()),
        "totalPrompts": sum(day["prompts"] for day in days.values()),
        "agentSeconds": sum(day["seconds"] for day in days.values()),
        "totalSessions": 171, "activeDays": len(days),
        "currentStreak": current, "longestStreak": longest,
        "peakTokens": max(day["tokens"] for day in days.values()),
        "files": 212, "partialFiles": 0,
    }


class UiTests(unittest.TestCase):
    def test_real_qml_view(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "backups/ui"
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="omarchy-statistics-ui-") as directory:
            harness = Path(directory)
            runtime = harness / "runtime"
            runtime.mkdir(mode=0o700)
            for name in ("Commons", "Ui", "services"):
                (harness / name).symlink_to(Path("/usr/share/omarchy/shell") / name)
            (harness / "Plugin").symlink_to(root)
            shutil.copyfile(root / "tests/UiHarness.qml", harness / "shell.qml")
            cache = harness / "cache"
            cache.mkdir()
            fixture = demonstration_snapshot()
            (cache / "summary.json").write_text(json.dumps(fixture))
            environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), OMARCHY_STATS_TEST_OUTPUT=str(output), OMARCHY_STATS_TEST_TOTAL_TOKENS=str(fixture["totalTokens"]))
            completed = subprocess.run(["quickshell", "-p", str(harness), "--no-color"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
            (output / "validation.log").write_text(completed.stdout)
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("UI_TEST_PASSED", completed.stdout)
            self.assertNotIn("UI_TEST_FAILED", completed.stdout)
            self.assertNotIn("Binding loop", completed.stdout)
            self.assertNotIn("Cannot specify", completed.stdout)
            self.assertTrue((output / "statistics-light.png").is_file())
            self.assertTrue((output / "statistics-dark.png").is_file())


if __name__ == "__main__":
    unittest.main()
