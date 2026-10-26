# LLM Context Capture Tool for TheAtom Kiosk

This debugging utility provides **non-intrusive, opt-in capture and analysis** of the exact payloads sent to every Large Language Model (LLM) invocation during manual kiosk testing.

It enables inspecting system instructions, customer context, conversation history, tool schemas, and provider usage metrics (token counts, queue times, reasoning tokens) without modifying prompts, tool definitions, or business logic.

---

## 1. Quick Start

### Step 1: Enable Context Capture
Set the environment variable in your terminal session before starting the backend:

```bash
export LLM_CONTEXT_CAPTURE=true
```

*(When unset or set to `false`, context capture is completely disabled with zero runtime overhead or disk writes).*

### Step 2: Start the Backend
Activate the virtual environment and launch the FastAPI server:

```bash
cd backend
source venv311/bin/activate
uvicorn api:app --reload --port 8000
```

*(Optional: In another terminal, start the frontend kiosk if testing via UI):*
```bash
cd frontend
npm run dev
```

---

## 2. Representative Manual Test Journey

Perform your manual kiosk interaction (via voice or text in the UI). For context debugging, use this representative 5-turn journey:

1. **Step 1:** Open the burger category (e.g. say *"Show me burgers"* or tap Burgers).
2. **Step 2:** Select Veg Makhani (e.g. say *"Can I get a Veg Makhani"*).
3. **Step 3:** Decline the meal offer (e.g. say *"No thanks, just the burger"*).
4. **Step 4:** Later accept the meal offer (e.g. say *"Actually, make that a meal"*).
5. **Step 5:** Swap the fries for Saucy Fries (e.g. say *"Swap the fries for saucy fries"*).

---

## 3. Finding Generated Captures

Captures are stored in `backend/debugging/captures/`:

```
backend/debugging/captures/
├── call_20261022_143015_perf_a1b2c3_t1_c1.json   # Single LLM invocation record
├── call_20261022_143018_perf_a1b2c3_t1_c2.json   # Follow-up LLM invocation within same turn
└── session_sess_d4e5f6.jsonl                      # Multi-turn session stream (1 JSON per line)
```

Each record contains:
- `metadata`: `interaction_id`, `session_id`, `turn_number`, `invocation_index`, `invocation_type` (`tool_selection` vs `followup_after_tool`), `model_name`, `provider`, `elapsed_time_seconds`.
- `context_breakdown`: System prompt, customer context, conversation history messages, tool schemas, estimated tokens.
- `raw_model_input`: The exact, unpruned message list and function schemas sent to the provider.
- `model_response`: The text response, tool calls triggered, and tool call IDs.
- `provider_usage`: Measured provider tokens (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`), plus provider latencies (`queue_time_seconds`, `prompt_time_seconds`, `completion_time_seconds`, `total_time_seconds`). Unavailable fields are marked explicitly as `"unavailable"`.

---

## 4. Generating & Reading Inspection Reports

Use the CLI script `backend/debugging/generate_report.py` to analyze captures and inspect token consumption, message sizes, stale tools, and diffs.

### Inspect the Latest Session:
```bash
python backend/debugging/generate_report.py --latest
```

### Save Report to a Markdown File:
```bash
python backend/debugging/generate_report.py --latest -o backend/debugging/captures/inspection_report.md
```

### Inspect a Specific Single Call:
```bash
python backend/debugging/generate_report.py backend/debugging/captures/call_20261022_143015_perf_a1b2c3_t1_c1.json
```

### Compare Consecutive Invocations (Diff Mode):
To see what changed between Call 1 (before tool execution) and Call 2 (after tool execution) or across turns:
```bash
python backend/debugging/generate_report.py --diff \
  backend/debugging/captures/call_20261022_143015_perf_a1b2c3_t1_c1.json \
  backend/debugging/captures/call_20261022_143018_perf_a1b2c3_t1_c2.json
```

The report provides:
- **Measured Provider Tokens vs Local Estimates** (`tiktoken` `cl100k_base`).
- **Section Breakdown**: Share of context taken by System Prompt, Customer Context, History, and Tool Schemas.
- **Ordered Message Breakdown**: Every message in order with tokens and preview.
- **Diagnostics**:
  - Largest messages in context.
  - Retained tool execution results (flagging artifacts from prior turns).
  - Redundant or repeated text blocks across messages.
- **Consecutive Diffs**: Token growth (+Δ%), new messages added, customer context diffs.

---

## 5. Disabling Capture & Cleanup

### Disable Capture
```bash
unset LLM_CONTEXT_CAPTURE
# or
export LLM_CONTEXT_CAPTURE=false
```

### Safely Delete Local Captures
Local capture dumps are git-ignored. To remove all captured debug records:

```bash
rm -f backend/debugging/captures/*.json backend/debugging/captures/*.jsonl backend/debugging/captures/*.md
```

---

## 6. Privacy & Safety Notice

- **Local Only:** This utility does not expose any HTTP endpoints or remote telemetry.
- **Credential Scrubbing:** API keys (`gsk_*`, `AIza*`, `sk-*`, `Bearer` tokens) are automatically redacted prior to writing files.
- **Sensitive Content:** Captured files contain verbatim user messages and tool outputs from your manual test sessions. Never commit capture files to shared repositories.
