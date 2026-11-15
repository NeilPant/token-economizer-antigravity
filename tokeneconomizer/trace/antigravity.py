"""Readers for Antigravity's JSONL conversation transcript.

The current CLI transcript records one object per trajectory step. Model steps carry
per-invocation token usage and tool calls; GENERIC steps carry tool results. This adapter
normalizes the stable observed fields into the Claude-shaped trace format consumed by the
shared learning stages. Unknown or incomplete records are skipped rather than guessed.
"""
import json
import os
from collections import Counter, deque
from tempfile import NamedTemporaryFile

from .jsonl import records


_TOKEN_FIELDS = {
    "input_tokens": "input_tokens",
    "cache_read_tokens": "cache_read_input_tokens",
    "cache_write_tokens": "cache_creation_input_tokens",
    "output_tokens": "output_tokens",
}


def _tool_name(name):
    return {
        "run_command": "Bash",
        "read_file": "Read",
        "view_file": "Read",
        "write_to_file": "Write",
        "replace_file_content": "Edit",
        "multi_replace_file_content": "MultiEdit",
    }.get(str(name or "").lower(), str(name or ""))


def _tool_args(name, args):
    args = args if isinstance(args, dict) else {}
    name = str(name or "").lower()
    if name == "run_command":
        return {"command": args.get("CommandLine") or args.get("command") or "",
                "cwd": args.get("Cwd") or args.get("cwd") or ""}
    if name in ("read_file", "view_file"):
        return {"file_path": args.get("AbsolutePath") or args.get("Path") or
                args.get("path") or ""}
    if name in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
        return {"file_path": args.get("TargetFile") or args.get("target_file") or
                args.get("path") or ""}
    return args


def _result_text(record):
    content = record.get("content")
    if isinstance(content, str):
        return content
    if content is not None:
        return json.dumps(content, ensure_ascii=False)
    if record.get("error"):
        return str(record["error"])
    return ""


def antigravity_to_claude(transcript_path, output_path):
    """Write a Claude-shaped JSONL trace from an Agy transcript; return records written.

    Transcript tool calls are paired with subsequent GENERIC steps within each prompt. Agy's
    hook payload remains the authoritative source for live failure status; this reader is for
    completed-session folding and intentionally does not infer success from missing output.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    output_dir = os.path.dirname(os.path.abspath(output_path))
    temporary_path = None
    try:
        os.makedirs(output_dir, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", errors="backslashreplace",
                                dir=output_dir, delete=False) as output:
            temporary_path = output.name
            count = 0
            for row in _claude_steps(records(transcript_path)):
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
        os.replace(temporary_path, output_path)
        temporary_path = None
        return count
    except OSError:
        return None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _claude_steps(rows):
    pending = deque()
    for row_number, row in enumerate(rows):
        kind = str(row.get("type") or "").upper()
        if kind == "USER_INPUT" and row.get("source") == "USER_EXPLICIT":
            pending.clear()  # A new prompt can follow an interrupted tool call.
            yield {"type": "user", "message": {"content": _result_text(row)}}
            continue
        if _is_model_step(row, kind):
            calls = row.get("tool_calls")
            calls = calls if isinstance(calls, list) else []
            blocks = []
            text = row.get("content")
            if isinstance(text, str) and text.strip():
                blocks.append({"type": "text", "text": text})
            for index, call in enumerate(calls):
                if not isinstance(call, dict):
                    continue
                tool_name = call.get("name") or call.get("toolName")
                tool_id = f"agy-row-{row_number}-{index}"
                blocks.append({"type": "tool_use", "id": tool_id,
                               "name": _tool_name(tool_name),
                               "input": _tool_args(tool_name, call.get("args"))})
                pending.append(tool_id)
            if blocks:
                yield {"type": "assistant", "message": {"content": blocks}}
            continue
        if kind == "GENERIC" and pending:
            tool_id = pending.popleft()
            result = _result_text(row)
            failed = str(row.get("status") or "").upper() in ("ERROR", "FAILED")
            if row.get("error"):
                failed = True
            yield {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": result,
                 "is_error": failed}
            ]}}


def _is_model_step(row, kind):
    return kind != "GENERIC" and (str(row.get("source") or "").upper() == "MODEL" or
                                  kind in ("MODEL", "PLANNER_RESPONSE"))


def antigravity_prompt_count(transcript_path):
    return sum(1 for row in records(transcript_path)
               if str(row.get("type") or "").upper() == "USER_INPUT"
               and row.get("source") == "USER_EXPLICIT")


def antigravity_session_usage(transcript_path):
    """Sum each step once, using the latest valid counter reported for each field."""
    by_step = {}
    for row_number, row in enumerate(records(transcript_path)):
        if not _is_model_step(row, str(row.get("type") or "").upper()):
            continue
        usage = {}
        for field, name in _TOKEN_FIELDS.items():
            value = row.get(field)
            if type(value) is int or (isinstance(value, float) and value.is_integer()):
                if value >= 0:
                    usage[name] = int(value)
        model = row.get("model") or row.get("modelName")
        step_index = row.get("step_index")
        key = step_index if type(step_index) in (int, str) else (row_number,)
        if usage:
            step = by_step.setdefault(key, {})
            step.update(usage)
            if isinstance(model, str) and model:
                step["model"] = model
    if not by_step:
        return {}
    models = Counter(step["model"] for step in by_step.values() if "model" in step)
    out = {name: sum(step.get(name, 0) for step in by_step.values()) for name in _TOKEN_FIELDS.values()}
    out["requests"] = len(by_step)
    out["model"] = models.most_common(1)[0][0] if models else None
    out["files"] = int(os.path.exists(transcript_path))
    return out
