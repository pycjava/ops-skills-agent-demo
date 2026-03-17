# Message Preprocess Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight preprocess policy layer that forces OCR-first handling for image-bearing chat turns and forwards OCR text into downstream analysis.

**Architecture:** Add a policy-resolution module plus a small orchestration wrapper around agent execution. The wrapper will run OCR internally for matched image policies, emit OCR status/result events, and then execute the downstream agent with OCR-enriched text and without re-attaching the raw images.

**Tech Stack:** Python, FastAPI WebSocket flow, pytest, existing agent runtime/orchestration utilities

---

## Chunk 1: Policy Resolution

### Task 1: Add failing tests for preprocess policy matching

**Files:**
- Create: `backend/tests/test_message_preprocess.py`
- Modify: `backend/services/message_preprocess.py`

- [ ] **Step 1: Write the failing test**

```python
def test_image_attachment_policy_routes_router_turns_to_supervisor_after_ocr():
    plan = resolve_message_preprocess_plan(...)
    assert plan.downstream_agent_id == "supervisor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_message_preprocess.py -q`
Expected: FAIL because `message_preprocess` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
def resolve_message_preprocess_plan(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_message_preprocess.py -q`
Expected: PASS

## Chunk 2: OCR-First Orchestration

### Task 2: Add failing tests for OCR-first execution order

**Files:**
- Modify: `backend/tests/test_message_preprocess.py`
- Modify: `backend/agent.py`
- Modify: `backend/services/conversation_attachments.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_run_agent_turn_runs_ocr_before_downstream_agent(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_message_preprocess.py -q`
Expected: FAIL because the orchestration wrapper is missing

- [ ] **Step 3: Write minimal implementation**

```python
async def run_agent_turn(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_message_preprocess.py -q`
Expected: PASS

## Chunk 3: WebSocket Integration

### Task 3: Persist OCR preprocessing results in chat history

**Files:**
- Modify: `backend/api/ws/chat.py`
- Modify: `backend/tests/test_chat_ocr_helpers.py`

- [ ] **Step 1: Write the failing test**

```python
def test_websocket_chat_handles_preprocessed_ocr_result_event(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_chat_ocr_helpers.py -q`
Expected: FAIL because `ocr_result` events are not persisted yet

- [ ] **Step 3: Write minimal implementation**

```python
elif etype == "ocr_result":
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_chat_ocr_helpers.py -q`
Expected: PASS

## Chunk 4: Verification

### Task 4: Run targeted regression checks

**Files:**
- Test: `backend/tests/test_message_preprocess.py`
- Test: `backend/tests/test_chat_ocr_helpers.py`
- Test: `backend/tests/test_multimodal_ocr_service.py`

- [ ] **Step 1: Run targeted backend tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_message_preprocess.py backend/tests/test_chat_ocr_helpers.py backend/tests/test_multimodal_ocr_service.py -q`
Expected: PASS

- [ ] **Step 2: Review event payloads and downstream agent selection**

Run: inspect test assertions and failure output if needed
Expected: image turns emit OCR result and continue through the downstream chain
