---
description: NovelForge engineering development rules (architectural elegance, low coupling, maintainability)
globs:
  - "backend/**/*.py"
  - "frontend/src/renderer/src/**/*.{ts,vue}"
  - "docs/**/*.md"
alwaysApply: true
---

# NovelForge Engineering Rule

## 0) Goal

All development behavior prioritizes "long-term maintainability" first:

1. Low coupling (clear module boundaries)
2. High cohesion (single responsibility)
3. Verifiable (changes have a validation loop)
4. Evolvable (avoid hardcoding everything at once)

Do not introduce hard-to-reclaim hardcoding and implicit behavior just to "get it running."

---

## 1) Architecture & Decoupling Rules

### 1.1 Event-Driven First

- Cross-domain linkage (e.g. "trigger a workflow after saving a card") must prefer event publish/subscribe.
- Do not directly chain multiple downstream modules in a business entry to form a "hard call chain."

### 1.2 Plugin-Style Registration First

- Extensible capabilities (initializers, workflow nodes, event handlers) must be registered via decorators.
- Adding a capability must complete the "two steps":
  1) Define and decorate
  2) Import in the corresponding `__init__.py` to ensure registration takes effect

### 1.3 Centralized Configuration Management

- All variable parameters must enter the unified configuration system (environment variables + config objects).
- Do not hardcode in business code: URLs, switches, thresholds, model names, timeouts, retry counts.

---

## 2) Service Layer & Interface Rules

### 2.1 Single Responsibility

- A service is responsible for only one domain.
- Split complex capabilities into "small services + a coordination layer"; no "giant god-class services."

### 2.2 Dependency Injection

- Inject `Session`, config, and dependency objects via parameters.
- Do not secretly create and long-term hold global dependency instances inside a function.

### 2.3 API Contract Single Source of Truth

- Type definitions take the back-end schema as the single source of truth.
- The front end must use OpenAPI-generated types; do not hand-write duplicate interface types and keep them around long-term.
- The front end should not rebuild back-end models or interface types; prefer generating and reusing them from the back end via `npm run gen:types`.
- Any API endpoint must declare a clear response model to ensure the contract is generatable.

---

## 3) Workflow System Rules

### 3.1 Code-Change Loop

- Any workflow code change must go through a "verifiable loop":
  1) generate new code/patch
  2) parse
  3) validate
  4) apply only after passing

- Do not skip validation and write directly to the database.

### 3.2 Visual-Editing Safety

- Visual parameter changes must not be written back by directly concatenating strings.
- Literal encoding/escaping must be handled correctly to avoid writing a legal value as erroneous code with extra quotes.
- Any front-end write-back must be confirmed via a server-side validation result.

### 3.3 Runtime-Capability Consistency

- Workflow feature design must consider:
  - Background-run visibility (global status feedback)
  - Node-level progress reporting
  - Pause/resume
  - Run-record retention policy (temporary vs. persistent)

- New features must not break the consistent semantics of the above capabilities.

---

## 4) Agent System Rules

### 4.1 Shared Layer vs. Business Layer Separation

- Generic message rendering, streaming events, and input-box interaction must reuse the shared layer.
- Business Agents only implement their own tools and strategies; do not copy a UI/protocol.

### 4.2 Single-Track Display, Avoid Dual Implementations

- The same semantics (e.g. message timeline) must not maintain two parallel display logics.
- If a new mode is genuinely needed, you must prove the old mode can't meet the need and provide a migration plan.

### 4.3 Runtime Dependencies Must Be Explicit

- When key runtime dependencies like prompts are missing, it should report an error explicitly.
- Do not add "only available in source-code directory" implicit fallback-read logic.

---

## 5) Frontend Engineering Rules

### 5.1 Component Size Control

- Oversized components must be continuously split (UI, state, event handling, data conversion separated).
- Prioritize extracting: shared components, composables, type definitions.

### 5.2 Dark Mode & Theming

- Styles must prefer theme variables.
- Do not hardcode light text that becomes unreadable in dark mode.

### 5.3 State & Event Consistency

- Any streaming interaction must have a clear state machine (idle/running/stopped/error).
- "Send/abort" must share one action entry; avoid dual-button state conflicts.

---

## 6) Data & Robustness Rules

### 6.1 Input Tolerance & Field Fallback

- Event payloads and node inputs must do defensive handling of required fields.
- Allow "multi-layer fallback parsing" for key fields to avoid a `None` breaking the whole chain.

### 6.2 Transactions & Exception Boundaries

- Failures must be rollback-able; no half-success dirty states.
- For degradable features (e.g. non-critical linkage), you may catch exceptions, but must log structured logs.

---

## 7) Coding & Change Rules

### 7.1 Minimum-Change Principle

- Only change files and logic related to the goal.
- No unrelated refactors, unrelated renames, or unrelated formatting noise.

### 7.2 Encoding & File Safety

- Text files uniformly use UTF-8.
- Do not rewrite a whole file without confirming the encoding; prefer local patches.

### 7.3 Forbidden Anti-Patterns

The following are forbidden:

- Copy-pasting isomorphic logic for "speed" (front/back end, between modules)
- Maintaining the same business rule in multiple places
- Replacing formal back-end validation with a front-end temporary string rule
- Exposing procedural debug switches long-term to users without product meaning

---

## 8) Validation & Delivery Rules

### 8.1 Required Validation

- Back-end changes: at least do target-API/flow-level verification.
- Front-end changes: at least do key-path interaction verification (load, submit, error branches).
- Workflow-related changes: must verify the full parse/validate/run chain.

### 8.2 Change Notes

- Delivery notes must include: change scope, behavior changes, verified content, known limitations.
- If there are unresolved edge issues, they must be explicitly marked, not hidden.

---

## 9) Decision Priority (on Conflict)

When multiple solutions can implement a feature, decide by the following priority:

1. Least destructive
2. Highest reusability
3. Most complete validation chain
4. Most consistent UX
5. Moderate implementation complexity

If the above can't all be met, ensure correctness and maintainability first, then optimize experience.
