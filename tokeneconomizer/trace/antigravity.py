"""Readers for Antigravity's JSONL conversation transcript.

The current CLI transcript records one object per trajectory step. Model steps carry
per-invocation token usage and tool calls; GENERIC steps carry tool results. This adapter
normalizes the stable observed fields into the Claude-shaped trace format consumed by the
shared learning stages. Unknown or incomplete records are skipped rather than guessed.
"""
import json
import os

from .jsonl import records


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

    Transcript tool calls are paired with subsequent GENERIC steps in trajectory order. Agy's
    hook payload remains the authoritative source for live failure status; this reader is for
    completed-session folding and intentionally does not infer success from missing output.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    rows = list(records(transcript_path))
    pending = []
    out = []
    for row in rows:
        kind = str(row.get("type") or "").upper()
        is_model = (kind != "GENERIC" and
                    (str(row.get("source") or "").upper() == "MODEL" or
                     kind in ("MODEL", "PLANNER_RESPONSE")))
        if kind == "USER_INPUT" and row.get("source") == "USER_EXPLICIT":
            out.append({"type": "user", "message": {"content": _result_text(row)}})
            continue
        if is_model:
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
                tool_id = f"agy-step-{row.get('step_index', len(out))}-{index}"
                blocks.append({"type": "tool_use", "id": tool_id,
                               "name": _tool_name(tool_name),
                               "input": _tool_args(tool_name, call.get("args"))})
                pending.append(tool_id)
            if blocks:
                out.append({"type": "assistant", "message": {"content": blocks}})
            continue
        if kind == "GENERIC" and pending:
            tool_id = pending.pop(0)
            result = _result_text(row)
            failed = str(row.get("status") or "").upper() in ("ERROR", "FAILED")
            if row.get("error"):
                failed = True
            out.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": result,
                 "is_error": failed}
            ]}})
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            for row in out:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return len(out)


def antigravity_prompt_count(transcript_path):
    return sum(1 for row in records(transcript_path)
               if str(row.get("type") or "").upper() == "USER_INPUT"
               and row.get("source") == "USER_EXPLICIT")


def antigravity_session_usage(transcript_path):
    """Sum model token usage once per trajectory step; absent fields remain unavailable."""
    by_step = {}
    models = {}
    for row in records(transcript_path):
        if ((str(row.get("source") or "").upper() != "MODEL" and
             str(row.get("type") or "").upper() not in ("MODEL", "PLANNER_RESPONSE")) or
                str(row.get("type") or "").upper() == "GENERIC"):
            continue
        if not any(isinstance(row.get(k), (int, float)) for k in (
                "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")):
            continue
        key = row.get("step_index")
        if key is None:
            key = f"row-{len(by_step)}"
        usage = {
            "input_tokens": int(row.get("input_tokens") or 0),
            "cache_read_input_tokens": int(row.get("cache_read_tokens") or 0),
            "cache_creation_input_tokens": int(row.get("cache_write_tokens") or 0),
            "output_tokens": int(row.get("output_tokens") or 0),
        }
        by_step[key] = usage
        model = row.get("model") or row.get("modelName")
        if model:
            models[str(model)] = models.get(str(model), 0) + 1
    if not by_step:
        return {}
    out = {name: sum(row[name] for row in by_step.values()) for name in (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
        "output_tokens")}
    out["requests"] = len(by_step)
    out["model"] = max(models, key=models.get) if models else None
    out["files"] = int(os.path.exists(transcript_path))
    return out
