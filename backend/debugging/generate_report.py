#!/usr/bin/env python3
"""
backend/debugging/generate_report.py
Human-readable inspection and analysis tool for captured LLM context records.

Reads raw JSON or JSONL captures and produces a detailed report covering:
- Metadata & provider timing
- Actual provider token usage vs estimated token counts
- Context section breakdown (system prompt, customer context, history, current turn, tool schemas)
- Message-by-message order and content
- Anomaly diagnostics: largest messages, stale tool results, duplicate text
- Step-by-step diff between consecutive LLM invocations
"""

import argparse
import difflib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from debugging.context_capture import estimate_tokens, get_captures_dir
except ImportError:
    # Handle direct execution from backend or debugging directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from debugging.context_capture import estimate_tokens, get_captures_dir


def load_capture_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load capture records from a JSON or JSONL file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Capture file not found: {file_path}")

    records = []
    if file_path.suffix == ".jsonl":
        with open(file_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: line {line_no} in {file_path.name} is invalid JSON: {e}", file=sys.stderr)
    elif file_path.suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}. Expected .json or .jsonl")

    return records


def find_latest_captures() -> List[Path]:
    """Find the most recent capture files in the captures directory."""
    captures_dir = get_captures_dir()
    if not captures_dir.exists():
        return []

    # Check for session jsonl first
    jsonl_files = sorted(captures_dir.glob("session_*.jsonl"), key=os.path.getmtime, reverse=True)
    if jsonl_files:
        return [jsonl_files[0]]

    # Fall back to json calls
    json_files = sorted(captures_dir.glob("call_*.json"), key=os.path.getmtime, reverse=True)
    return json_files[:10]


def format_token_val(val: Any) -> str:
    """Format token measurement or mark as unavailable."""
    if val is None or val == "unavailable":
        return "*Unavailable*"
    if isinstance(val, (int, float)):
        return f"{val:,}" if isinstance(val, int) else f"{val:.2f}"
    return str(val)


def format_time_val(val: Any) -> str:
    """Format seconds into milliseconds or mark as unavailable."""
    if val is None or val == "unavailable":
        return "*Unavailable*"
    try:
        f_val = float(val)
        return f"{f_val * 1000.0:.2f} ms ({f_val:.4f} s)"
    except (ValueError, TypeError):
        return str(val)


def detect_duplicates(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify repeated or duplicated content across context messages."""
    seen_snippets = {}
    duplicates = []

    for msg in messages:
        content = msg.get("content") or ""
        if not isinstance(content, str) or len(content.strip()) < 20:
            continue

        # Check for paragraph-level duplication
        paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) >= 30]
        for p in paragraphs:
            # Normalize whitespace
            norm = " ".join(p.split())
            if norm in seen_snippets:
                duplicates.append({
                    "snippet": norm[:80] + ("..." if len(norm) > 80 else ""),
                    "first_seen_role": seen_snippets[norm]["role"],
                    "first_seen_index": seen_snippets[norm]["index"],
                    "repeated_in_role": msg.get("role"),
                    "repeated_in_index": msg.get("index"),
                    "length_chars": len(norm),
                })
            else:
                seen_snippets[norm] = {"role": msg.get("role"), "index": msg.get("index")}

    return duplicates


def detect_stale_tool_results(
    messages: List[Dict[str, Any]], current_turn: int
) -> List[Dict[str, Any]]:
    """Flag tool messages from prior turns that remain in context."""
    stale_results = []
    # If messages don't have explicit turn info, inspect position relative to user messages
    user_turn_counter = 0
    for idx, msg in enumerate(messages):
        if msg.get("role") == "user":
            user_turn_counter += 1
        elif msg.get("role") == "tool":
            is_prior_turn = (user_turn_counter < current_turn) if current_turn > 1 else False
            content = str(msg.get("content") or "")
            stale_results.append({
                "message_index": idx,
                "tool_call_id": msg.get("tool_call_id"),
                "estimated_tokens": msg.get("estimated_tokens", estimate_tokens(content)),
                "is_prior_turn": is_prior_turn,
                "turn_observed": user_turn_counter,
                "content_preview": content[:120] + ("..." if len(content) > 120 else ""),
            })
    return stale_results


def generate_single_call_report(record: Dict[str, Any]) -> str:
    """Generate a comprehensive markdown report for a single captured invocation."""
    meta = record.get("metadata", {})
    breakdown = record.get("context_breakdown", {})
    sys_info = breakdown.get("system_instructions", {})
    curr_turn = breakdown.get("current_turn", {})
    history_msgs = breakdown.get("conversation_history_messages", [])
    tools = breakdown.get("tool_definitions", [])
    usage = record.get("provider_usage", {})
    resp = record.get("model_response", {})

    lines = []
    lines.append(f"# LLM Invocation Report — {record.get('capture_id', 'Unknown ID')}")
    lines.append("")
    lines.append(f"- **Timestamp (UTC):** {record.get('timestamp_utc', 'Unknown')}")
    lines.append(f"- **Interaction ID:** `{meta.get('interaction_id', 'unavailable')}`")
    lines.append(f"- **Session ID:** `{meta.get('session_id', 'unavailable')}`")
    lines.append(f"- **Turn Number:** {meta.get('turn_number', 1)}")
    lines.append(f"- **Invocation Index within Turn:** {meta.get('invocation_index', 1)}")
    lines.append(f"- **Invocation Type:** `{meta.get('invocation_type', 'unknown')}`")
    lines.append(f"- **Model:** `{meta.get('model_name', 'unknown')}` ({meta.get('provider', 'groq')})")
    lines.append(f"- **Total Elapsed Time:** {meta.get('elapsed_time_seconds', 0.0):.4f} seconds")
    lines.append("")

    # Provider Usage vs Estimates
    lines.append("## 1. Provider Usage vs Estimated Tokens")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> Actual token counts are reported directly by the provider API. Estimated tokens are computed locally using `tiktoken` (`cl100k_base`).")
    lines.append("")
    lines.append("| Metric | Measured by Provider | Local Estimate (`cl100k_base`) |")
    lines.append("| :--- | :--- | :--- |")
    lines.append(f"| **Prompt Tokens** | **{format_token_val(usage.get('prompt_tokens'))}** | **~{breakdown.get('total_estimated_prompt_tokens', 0):,}** *(est.)* |")
    lines.append(f"| **Completion Tokens** | **{format_token_val(usage.get('completion_tokens'))}** | ~{estimate_tokens(str(resp.get('content', ''))):,} *(est.)* |")
    lines.append(f"| **Reasoning Tokens** | **{format_token_val(usage.get('reasoning_tokens'))}** | *N/A (model internal)* |")
    lines.append(f"| **Total Tokens** | **{format_token_val(usage.get('total_tokens'))}** | ~{breakdown.get('total_estimated_prompt_tokens', 0) + estimate_tokens(str(resp.get('content', ''))):,} *(est.)* |")
    lines.append(f"| **Prompt / Queue Time** | Queue: {format_time_val(usage.get('queue_time_seconds'))} <br> Prompt: {format_time_val(usage.get('prompt_time_seconds'))} | *N/A* |")
    lines.append(f"| **Completion / Total Time** | Comp: {format_time_val(usage.get('completion_time_seconds'))} <br> Total: {format_time_val(usage.get('total_time_seconds'))} | Measured duration: {meta.get('elapsed_time_seconds', 0.0):.3f}s |")
    lines.append("")

    # Section Breakdown
    lines.append("## 2. Context Section Breakdown")
    lines.append("")
    sys_est = sys_info.get("system_prompt_estimated_tokens", 0)
    cust_est = sys_info.get("customer_context_estimated_tokens", 0)
    user_est = curr_turn.get("user_input_estimated_tokens", 0)

    # Calculate tools token estimate
    tools_json = json.dumps(tools) if tools else ""
    tools_est = estimate_tokens(tools_json)

    # History estimate (excluding first two system messages and current user input)
    hist_est = sum(m.get("estimated_tokens", 0) for m in history_msgs[2:-1]) if len(history_msgs) > 3 else 0

    total_est = sys_est + cust_est + hist_est + user_est + tools_est

    def pct(part, tot):
        return f"{(part / tot * 100.0):.1f}%" if tot > 0 else "0.0%"

    lines.append("| Section | Messages / Schemas | Estimated Tokens (`cl100k_base`) | Share of Total |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| **Base System Prompt** | 1 SystemMessage | ~{sys_est:,} | {pct(sys_est, total_est)} |")
    lines.append(f"| **Customer Context System Message** | 1 SystemMessage | ~{cust_est:,} | {pct(cust_est, total_est)} |")
    lines.append(f"| **Conversation History** | {max(0, len(history_msgs) - 3)} messages | ~{hist_est:,} | {pct(hist_est, total_est)} |")
    lines.append(f"| **Current Turn Customer Input** | 1 HumanMessage | ~{user_est:,} | {pct(user_est, total_est)} |")
    lines.append(f"| **Tool Definitions (Schemas)** | {len(tools)} tool schemas | ~{tools_est:,} | {pct(tools_est, total_est)} |")
    lines.append(f"| **TOTAL INPUT CONTEXT** | **{len(history_msgs)} msgs + {len(tools)} tools** | **~{total_est:,}** | **100%** |")
    lines.append("")

    # Message Breakdown Table
    lines.append("## 3. Ordered Message Breakdown")
    lines.append("")
    lines.append("| # | Role | Message Type | Est. Tokens | Preview / Action |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")

    for m in history_msgs:
        idx = m.get("index", 0)
        role = m.get("role", "unknown")
        mtype = m.get("type", "unknown")
        tokens = m.get("estimated_tokens", 0)
        content = str(m.get("content") or "").replace("\n", " ")
        if len(content) > 75:
            preview = content[:72] + "..."
        else:
            preview = content or "*(empty content)*"

        tool_calls = m.get("tool_calls")
        if tool_calls:
            calls_str = ", ".join(f"{c.get('name')}({json.dumps(c.get('args', {}))})" for c in tool_calls)
            preview += f" <br> 🛠️ **Calls:** `{calls_str}`"

        tool_call_id = m.get("tool_call_id")
        if tool_call_id:
            preview = f"🛠️ `[{tool_call_id}]` {preview}"

        lines.append(f"| {idx} | `{role}` | `{mtype}` | ~{tokens:,} | {preview} |")
    lines.append("")

    # Diagnostics & Anomalies
    lines.append("## 4. Context Diagnostics & Anomaly Detection")
    lines.append("")

    # 4.1 Largest Messages
    sorted_msgs = sorted(history_msgs, key=lambda m: m.get("estimated_tokens", 0), reverse=True)
    lines.append("### 4.1 Largest Context Items")
    lines.append("")
    for i, m in enumerate(sorted_msgs[:3], 1):
        lines.append(f"{i}. **Msg #{m.get('index')} ({m.get('role')} / {m.get('type')})**: ~{m.get('estimated_tokens', 0):,} tokens")
        content_snippet = str(m.get("content") or "")[:200].replace("\n", " ")
        lines.append(f"   > {content_snippet}...")
    lines.append("")

    # 4.2 Stale Tool Results
    stale = detect_stale_tool_results(history_msgs, meta.get("turn_number", 1))
    lines.append("### 4.2 Tool Results Retained in Context")
    if stale:
        lines.append(f"Found **{len(stale)}** tool execution results in context:")
        lines.append("")
        for s in stale:
            flag = "⚠️ **(Prior turn artifact)**" if s["is_prior_turn"] else "✅ (Current turn)"
            lines.append(f"- **Msg #{s['message_index']}**: ~{s['estimated_tokens']} tokens | {flag} | Preview: `{s['content_preview']}`")
    else:
        lines.append("*No tool execution results in this context.*")
    lines.append("")

    # 4.3 Duplication Detection
    dups = detect_duplicates(history_msgs)
    lines.append("### 4.3 Redundant or Repeated Snippets")
    if dups:
        lines.append(f"⚠️ Found **{len(dups)}** repeated text snippets across messages:")
        lines.append("")
        for d in dups[:5]:
            lines.append(f"- `{d['snippet']}`")
            lines.append(f"  First seen in #{d['first_seen_index']} (`{d['first_seen_role']}`), repeated in #{d['repeated_in_index']} (`{d['repeated_in_role']}`)")
    else:
        lines.append("✅ *No significant duplicate text blocks detected.*")
    lines.append("")

    # Response & Tools Called
    lines.append("## 5. Model Output for This Invocation")
    lines.append("")
    if resp.get("tool_calls"):
        lines.append("### Tool Calls Triggered:")
        for tc in resp.get("tool_calls", []):
            lines.append(f"- **Tool:** `{tc.get('name')}` (ID: `{tc.get('id')}`)")
            lines.append(f"  **Arguments:** ```json\n{json.dumps(tc.get('args', {}), indent=2)}\n```")
    if resp.get("content"):
        lines.append("### Assistant Text Response:")
        lines.append(f"> {resp.get('content')}")
    lines.append("")

    # Detailed System Prompt & Customer Context
    lines.append("## 6. Context Details (Full Inspection)")
    lines.append("")
    lines.append("### 6.1 Customer Context Sent to Model")
    lines.append("```text")
    lines.append(sys_info.get("customer_context") or "None")
    lines.append("```")
    lines.append("")
    lines.append("### 6.2 Tool Schemas Available to Model")
    for t in tools:
        fn = t.get("function", {})
        lines.append(f"- **`{fn.get('name')}`**: {fn.get('description', '').strip().replace(chr(10), ' ')}")
        props = list(fn.get("parameters", {}).get("properties", {}).keys())
        req = fn.get("parameters", {}).get("required", [])
        lines.append(f"  - Parameters: `{props}` (required: `{req}`)")
    lines.append("")

    return "\n".join(lines)


def generate_diff_report(call_a: Dict[str, Any], call_b: Dict[str, Any]) -> str:
    """Compare two consecutive LLM invocations and produce a detailed diff report."""
    meta_a = call_a.get("metadata", {})
    meta_b = call_b.get("metadata", {})

    msgs_a = call_a.get("context_breakdown", {}).get("conversation_history_messages", [])
    msgs_b = call_b.get("context_breakdown", {}).get("conversation_history_messages", [])

    usage_a = call_a.get("provider_usage", {})
    usage_b = call_b.get("provider_usage", {})

    lines = []
    lines.append("# LLM Context Diff: Consecutive Invocation Comparison")
    lines.append("")
    lines.append(f"- **Call A:** Turn {meta_a.get('turn_number')}, Call #{meta_a.get('invocation_index')} (`{meta_a.get('invocation_type')}`) at {call_a.get('timestamp_utc')}")
    lines.append(f"- **Call B:** Turn {meta_b.get('turn_number')}, Call #{meta_b.get('invocation_index')} (`{meta_b.get('invocation_type')}`) at {call_b.get('timestamp_utc')}")
    lines.append("")

    # Token Growth Comparison
    tokens_a = usage_a.get("prompt_tokens") or call_a.get("context_breakdown", {}).get("total_estimated_prompt_tokens", 0)
    tokens_b = usage_b.get("prompt_tokens") or call_b.get("context_breakdown", {}).get("total_estimated_prompt_tokens", 0)

    try:
        delta_tokens = int(tokens_b) - int(tokens_a)
        pct_growth = (delta_tokens / int(tokens_a) * 100.0) if int(tokens_a) > 0 else 0.0
        growth_str = f"+{delta_tokens:,} tokens (+{pct_growth:.1f}%)" if delta_tokens >= 0 else f"{delta_tokens:,} tokens ({pct_growth:.1f}%)"
    except (ValueError, TypeError):
        growth_str = "N/A"

    lines.append("## 1. Context Growth Summary")
    lines.append("")
    lines.append("| Metric | Call A | Call B | Difference |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| **Prompt Tokens** | {format_token_val(tokens_a)} | {format_token_val(tokens_b)} | **{growth_str}** |")
    lines.append(f"| **Total Messages** | {len(msgs_a)} | {len(msgs_b)} | +{len(msgs_b) - len(msgs_a)} messages |")
    lines.append(f"| **Elapsed LLM Time** | {meta_a.get('elapsed_time_seconds', 0):.3f}s | {meta_b.get('elapsed_time_seconds', 0):.3f}s | {meta_b.get('elapsed_time_seconds', 0) - meta_a.get('elapsed_time_seconds', 0):+.3f}s |")
    lines.append("")

    # Messages Added Between Calls
    lines.append("## 2. Messages Added to Context Between Call A and Call B")
    lines.append("")
    if len(msgs_b) > len(msgs_a):
        new_msgs = msgs_b[len(msgs_a):]
        lines.append(f"Added **{len(new_msgs)}** new message(s):")
        lines.append("")
        for m in new_msgs:
            lines.append(f"- **#{m.get('index')} `{m.get('role')}` (`{m.get('type')}`)** [~{m.get('estimated_tokens', 0)} est. tokens]")
            content = str(m.get("content") or "")
            if m.get("tool_calls"):
                lines.append(f"  - 🛠️ Tool calls: `{json.dumps(m.get('tool_calls'))}`")
            elif m.get("tool_call_id"):
                lines.append(f"  - 🛠️ Tool result for `{m.get('tool_call_id')}`: ```\n{content[:300]}\n```")
            else:
                lines.append(f"  - Content: > {content[:200]}")
    else:
        lines.append("*No new messages added (message count remained constant or decreased).*")
    lines.append("")

    # Customer Context Diff
    cust_a = call_a.get("context_breakdown", {}).get("system_instructions", {}).get("customer_context") or ""
    cust_b = call_b.get("context_breakdown", {}).get("system_instructions", {}).get("customer_context") or ""

    lines.append("## 3. Customer Context Changes")
    lines.append("")
    if cust_a == cust_b:
        lines.append("✅ *Customer context system message is identical between both invocations.*")
    else:
        lines.append("⚠️ *Customer context changed between invocations:*")
        lines.append("```diff")
        diff = difflib.unified_diff(
            cust_a.splitlines(keepends=True),
            cust_b.splitlines(keepends=True),
            fromfile="Call A Customer Context",
            tofile="Call B Customer Context",
            n=2,
        )
        lines.extend("".join(diff).splitlines())
        lines.append("```")
    lines.append("")

    return "\n".join(lines)


def generate_session_summary_report(records: List[Dict[str, Any]]) -> str:
    """Generate a high-level summary report for an entire test session."""
    if not records:
        return "# LLM Context Capture: No records found.\n"

    lines = []
    lines.append(f"# LLM Context Capture: Session Summary ({len(records)} Invocations)")
    lines.append("")
    session_id = records[0].get("metadata", {}).get("session_id", "unknown")
    lines.append(f"- **Session ID:** `{session_id}`")
    lines.append(f"- **Total LLM Calls:** {len(records)}")
    first_time = records[0].get("timestamp_utc", "")
    last_time = records[-1].get("timestamp_utc", "")
    lines.append(f"- **Time Span:** {first_time} → {last_time}")
    lines.append("")

    lines.append("## 1. Invocation Sequence")
    lines.append("")
    lines.append("| Call # | Turn | Type | Actual Prompt Tokens | Est. Tokens | Completion Tokens | Duration | Tool Calls Triggered |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    for i, rec in enumerate(records, 1):
        meta = rec.get("metadata", {})
        usage = rec.get("provider_usage", {})
        breakdown = rec.get("context_breakdown", {})
        resp = rec.get("model_response", {})

        actual_prompt = format_token_val(usage.get("prompt_tokens"))
        est_prompt = f"~{breakdown.get('total_estimated_prompt_tokens', 0):,}"
        comp = format_token_val(usage.get("completion_tokens"))
        dur = f"{meta.get('elapsed_time_seconds', 0.0):.2f}s"
        tcalls = resp.get("tool_calls")
        tc_str = ", ".join(tc.get("name") for tc in tcalls) if tcalls else "*(none)*"

        lines.append(f"| {i} | Turn {meta.get('turn_number')} | `{meta.get('invocation_type')}` | **{actual_prompt}** | {est_prompt} | {comp} | {dur} | `{tc_str}` |")
    lines.append("")

    # Detailed report for each call
    for i, rec in enumerate(records, 1):
        lines.append("---")
        lines.append(f"## Call {i} of {len(records)}")
        lines.append("")
        lines.append(generate_single_call_report(rec))
        lines.append("")

    # Pairwise diffs
    if len(records) > 1:
        lines.append("---")
        lines.append("# Consecutive Invocation Comparisons (Diffs)")
        lines.append("")
        for i in range(len(records) - 1):
            lines.append(f"## Diff: Call {i+1} → Call {i+2}")
            lines.append("")
            lines.append(generate_diff_report(records[i], records[i+1]))
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze and inspect captured LLM context records.")
    parser.add_argument("path", nargs="?", help="Path to capture file (.json or .jsonl) or directory.")
    parser.add_argument("--latest", action="store_true", help="Automatically inspect the most recent capture.")
    parser.add_argument("--diff", nargs=2, metavar=("CALL1", "CALL2"), help="Generate diff between two specific call json files.")
    parser.add_argument("--output", "-o", help="Write report to markdown file instead of stdout.")
    args = parser.parse_args()

    # 1. Diff mode
    if args.diff:
        path_a = Path(args.diff[0])
        path_b = Path(args.diff[1])
        recs_a = load_capture_file(path_a)
        recs_b = load_capture_file(path_b)
        if not recs_a or not recs_b:
            print("Error: Could not load one or both diff files.", file=sys.stderr)
            sys.exit(1)
        report = generate_diff_report(recs_a[0], recs_b[0])

    # 2. Latest mode
    elif args.latest or not args.path:
        latest_files = find_latest_captures()
        if not latest_files:
            print("No capture files found in backend/debugging/captures/.", file=sys.stderr)
            print("To enable capture, set: export LLM_CONTEXT_CAPTURE=true", file=sys.stderr)
            sys.exit(1)
        target = latest_files[0]
        print(f"Loading latest capture: {target.name}...", file=sys.stderr)
        records = load_capture_file(target)
        if len(records) == 1:
            report = generate_single_call_report(records[0])
        else:
            report = generate_session_summary_report(records)

    # 3. Path mode
    else:
        target_path = Path(args.path)
        records = load_capture_file(target_path)
        if len(records) == 1:
            report = generate_single_call_report(records[0])
        else:
            report = generate_session_summary_report(records)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report written to: {out_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
