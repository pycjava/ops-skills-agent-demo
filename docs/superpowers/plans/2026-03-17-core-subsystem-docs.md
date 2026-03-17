# Core Subsystem Docs Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 new system design / roadmap documents for the missing core subsystems and update the `docs/README.md` index.

**Architecture:** Keep the existing `docs/system-desigin/` structure intact and add one `*-design.md` plus one `*-roadmap.md` per missing subsystem. Reuse a consistent template so the new documents read as one documentation set instead of isolated notes.

**Tech Stack:** Markdown, existing repository docs under `docs/system-desigin/`, FastAPI/Vue codebase as source material

---

## Chunk 1: Planning And File Map

### Task 1: Confirm file responsibilities

**Files:**
- Create: `docs/system-desigin/conversation-design.md`
- Create: `docs/system-desigin/conversation-roadmap.md`
- Create: `docs/system-desigin/capability-extension-design.md`
- Create: `docs/system-desigin/capability-extension-roadmap.md`
- Create: `docs/system-desigin/memory-and-reports-design.md`
- Create: `docs/system-desigin/memory-and-reports-roadmap.md`
- Create: `docs/system-desigin/auth-and-permissions-design.md`
- Create: `docs/system-desigin/auth-and-permissions-roadmap.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Map the scope**

Document that:
- `conversation-*` covers conversation state, messages, attachments, WS chat, and task run playback
- `capability-extension-*` covers Skills + MCP registration, binding, runtime injection, and UI surfaces
- `memory-and-reports-*` covers `/memories/`, reports, notifications, and RAG synchronization boundaries
- `auth-and-permissions-*` covers auth settings, session-based login, RBAC, REST/WS permission checks, and login UI

- [ ] **Step 2: Verify current docs do not already cover these as standalone files**

Run: `Get-ChildItem docs/system-desigin`
Expected: no existing standalone files for those four subsystems

## Chunk 2: Conversation Docs

### Task 2: Write conversation design and roadmap docs

**Files:**
- Create: `docs/system-desigin/conversation-design.md`
- Create: `docs/system-desigin/conversation-roadmap.md`

- [ ] **Step 1: Draft `conversation-design.md`**

Include:
- background and goals
- subsystem boundary
- module responsibilities across models, services, routers, store domains, and components
- key flows for `init`, `message`, `clear`, `abort`, history loading, and attachment snapshots
- REST/WS interface summary
- defaults, fallbacks, and tradeoffs

- [ ] **Step 2: Draft `conversation-roadmap.md`**

Include:
- current state and current gaps
- the 4 agreed phases
- stage entry criteria
- risk and priority summary
- next implementation suggestions

- [ ] **Step 3: Verify both files render as expected**

Run: `Get-Content docs/system-desigin/conversation-design.md`
Expected: required sections present with no placeholder text

Run: `Get-Content docs/system-desigin/conversation-roadmap.md`
Expected: required sections present with all four phases

## Chunk 3: Capability Extension Docs

### Task 3: Write capability extension design and roadmap docs

**Files:**
- Create: `docs/system-desigin/capability-extension-design.md`
- Create: `docs/system-desigin/capability-extension-roadmap.md`

- [ ] **Step 1: Draft `capability-extension-design.md`**

Include:
- Skills catalog loading
- MCP config parsing, testing, and agent binding
- runtime injection through `AgentManager`
- current file-based MCP source of truth and UI surfaces

- [ ] **Step 2: Draft `capability-extension-roadmap.md`**

Include:
- current lightweight governance model
- 4 agreed phases around registration, testing, access control, and standardization
- risks from cache invalidation, audit gaps, and file-centric config

- [ ] **Step 3: Verify both files render as expected**

Run: `Get-Content docs/system-desigin/capability-extension-design.md`
Expected: required sections present with Skills and MCP both covered

Run: `Get-Content docs/system-desigin/capability-extension-roadmap.md`
Expected: required sections present with all four phases

## Chunk 4: Memory And Reports Docs

### Task 4: Write memory / reports design and roadmap docs

**Files:**
- Create: `docs/system-desigin/memory-and-reports-design.md`
- Create: `docs/system-desigin/memory-and-reports-roadmap.md`

- [ ] **Step 1: Draft `memory-and-reports-design.md`**

Include:
- `/memories/` store model and path normalization
- tree/content/delete APIs
- report generation and download path
- notification linkage and RAG sync boundaries

- [ ] **Step 2: Draft `memory-and-reports-roadmap.md`**

Include:
- current document-tree limitations
- metadata and retention gaps
- 4 agreed phases around normalization, metadata, structure, and stronger integration

- [ ] **Step 3: Verify both files render as expected**

Run: `Get-Content docs/system-desigin/memory-and-reports-design.md`
Expected: required sections present with memory and reports both covered

Run: `Get-Content docs/system-desigin/memory-and-reports-roadmap.md`
Expected: required sections present with all four phases

## Chunk 5: Auth Docs And Index Update

### Task 5: Write auth docs and update doc index

**Files:**
- Create: `docs/system-desigin/auth-and-permissions-design.md`
- Create: `docs/system-desigin/auth-and-permissions-roadmap.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Draft `auth-and-permissions-design.md`**

Include:
- env-driven auth configuration
- session middleware and session keys
- OIDC and password login
- role / permission seeding
- REST and WebSocket guards
- frontend auth state and login page

- [ ] **Step 2: Draft `auth-and-permissions-roadmap.md`**

Include:
- current opt-in RBAC model
- unified boundary and audit gaps
- 4 agreed phases around hardening, governance, and stronger isolation

- [ ] **Step 3: Update `docs/README.md`**

Add:
- the 8 new documents to the system design index
- updated recommended reading order

- [ ] **Step 4: Verify final file set**

Run: `Get-ChildItem docs/system-desigin`
Expected: 8 new files visible

Run: `git status --short docs/system-desigin docs/README.md docs/superpowers/specs docs/superpowers/plans`
Expected: only the intended new/modified docs listed for this work
