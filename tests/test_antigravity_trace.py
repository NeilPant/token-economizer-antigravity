import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tokeneconomizer.trace.antigravity import antigravity_session_usage, antigravity_to_claude


class AntigravityConversionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.transcript = Path(directory.name) / "input.jsonl"
        self.output = Path(directory.name) / "output.jsonl"

    def test_new_prompt_discards_unfinished_calls_and_keeps_tool_ids_unique(self):
        rows = [
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Read two files"},
            {"type": "MODEL", "step_index": 1, "tool_calls": [{"name": "read_file"}, {"name": "read_file"}]},
            {"type": "GENERIC", "content": "First result"},
            {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Read a third file"},
            {"type": "MODEL", "step_index": 1, "tool_calls": [{"name": "read_file"}]},
            {"type": "GENERIC", "status": "FAILED", "error": "File not found"},
        ]
        self.transcript.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

        count = antigravity_to_claude(self.transcript, self.output)

        self.assertEqual(count, 6)
        steps = [json.loads(line)["message"]["content"] for line in self.output.read_text(encoding="utf-8").splitlines()]
        first, interrupted = steps[1]
        third = steps[4][0]
        self.assertEqual(len({first["id"], interrupted["id"], third["id"]}), 3)
        self.assertEqual(steps[2][0]["tool_use_id"], first["id"])
        self.assertEqual(steps[5][0]["tool_use_id"], third["id"])
        self.assertEqual(steps[5][0]["content"], "File not found")
        self.assertTrue(steps[5][0]["is_error"])

    def test_failed_replacement_leaves_existing_output_and_cleans_up(self):
        self.transcript.write_text('{"type":"MODEL","content":"new"}\n', encoding="utf-8")
        self.output.write_text("previous\n", encoding="utf-8")

        with patch("tokeneconomizer.trace.antigravity.os.replace", side_effect=OSError("write failed")):
            self.assertIsNone(antigravity_to_claude(self.transcript, self.output))

        self.assertEqual(self.output.read_text(encoding="utf-8"), "previous\n")
        self.assertEqual(set(self.output.parent.iterdir()), {self.transcript, self.output})


class AntigravityUsageTests(unittest.TestCase):
    def read_usage(self, *rows):
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "transcript.jsonl"
            transcript.write_text(
                "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows),
                encoding="utf-8",
            )
            return antigravity_session_usage(transcript)

    def test_step_updates_preserve_counters_and_count_each_model_once(self):
        usage = self.read_usage(
            {"type": "MODEL", "step_index": 1, "model": "model-a", "input_tokens": 10, "output_tokens": 2},
            {"type": "MODEL", "step_index": 1, "model": "model-a", "output_tokens": 4},
            {"type": "MODEL", "step_index": 1, "model": "model-a", "cache_read_tokens": 5},
            {"type": "PLANNER_RESPONSE", "step_index": 2, "modelName": "model-b", "input_tokens": 6},
            {"source": "MODEL", "step_index": 3, "model": "model-b", "input_tokens": 7, "cache_write_tokens": 2},
            {"type": "GENERIC", "source": "MODEL", "step_index": 4, "input_tokens": 99},
        )

        self.assertEqual(usage, {
            "input_tokens": 23,
            "cache_read_input_tokens": 5,
            "cache_creation_input_tokens": 2,
            "output_tokens": 4,
            "requests": 3,
            "model": "model-b",
            "files": 1,
        })

    def test_malformed_fields_and_missing_step_ids_do_not_drop_valid_usage(self):
        usage = self.read_usage(
            {"type": "MODEL", "step_index": "row-1", "input_tokens": 4},
            {"type": "MODEL", "input_tokens": 3.0, "output_tokens": "invalid"},
            {"type": "MODEL", "step_index": [], "input_tokens": True, "output_tokens": 2},
            {"type": "MODEL", "step_index": 5, "input_tokens": -1, "output_tokens": float("inf")},
            "{partial line",
        )

        self.assertEqual(usage["input_tokens"], 7)
        self.assertEqual(usage["output_tokens"], 2)
        self.assertEqual(usage["requests"], 3)
        self.assertIsNone(usage["model"])

    def test_returns_no_usage_when_no_valid_counters_exist(self):
        self.assertEqual(self.read_usage(
            {"type": "USER_INPUT"},
            {"type": "MODEL", "input_tokens": False, "output_tokens": 1.5},
        ), {})
