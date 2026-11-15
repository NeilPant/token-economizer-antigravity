import json
import tempfile
import unittest
from pathlib import Path

from tokeneconomizer.trace.antigravity import antigravity_session_usage


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
