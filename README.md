<div align="center">

# NovelForge

<p><strong>A next-generation AI long-form novel writing engine</strong></p>

<p>
  <a href="#table-of-contents">Contents</a> •
  <a href="#core-features">Features</a> •
  <a href="#changelog">Changelog</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#creation-workflow">Creation Workflow</a>
</p>

<p>
  <a href="#advanced-features">Advanced</a> •
  <a href="#workflow-system">Workflow System</a> •
  <a href="#project-structure">Project Structure</a> •
  <a href="./CONTRIBUTING.md">Contributing</a> •
  <a href="./ROADMAP.md">Roadmap</a>
</p>


</div>

> ## ℹ️ English Fork Notice
>
> This is an **English-language fork** of [NovelForge](https://github.com/RhythmicWave/NovelForge), originally created and maintained by **[RhythmicWave](https://github.com/RhythmicWave)**.
>
> - The original project is in **Chinese**. This fork localizes the UI, documentation, and seed content to **English**.
> - This is **not** a 1:1 copy — some features, labels, or behaviors may differ from the upstream Chinese version as part of the localization process.
> - **I am not a coder.** This English migration was produced **100% by AI** assistance. Expect rough edges, and please report issues if you spot anything off.

---

**NovelForge** is an AI-assisted writing tool capable of producing long-form novels of hundreds of thousands or even millions of words. It is more than an editor — it is a complete solution combining world-building and structured content generation.

In long-form writing, the greatest challenges are maintaining consistency, ensuring controllability, and sustaining inspiration. To address these, NovelForge is built around four core concepts: modular **"Cards"**, customizable **"Dynamic Output Models"**, flexible **"Context Injection"**, and consistency-preserving **"Knowledge Graph"**.

---

<a id="table-of-contents"></a>
## 📑 Contents

### Quick Navigation

- [✨ Core Features](#core-features)
- [📅 Changelog](#changelog)
- [🛠️ Tech Stack](#tech-stack)
- [🚀 Getting Started](#getting-started)
- [✍️ Creation Workflow](#creation-workflow)
- [⚙️ Advanced Features & Configuration](#advanced-features)
- [📂 Project Structure](#project-structure)
- [🔭 Outlook](#outlook)

### Jump to Feature

- [Schema-first: Type/Instance Structure & Parameters](#schema-first)
- [Prompt Workshop](#prompt-workshop)
- [Context Injection (@DSL) in Depth](#context-dsl)
- [Workflow System (Code-style Workflows + Workflow Agent)](#workflow-system)
  - [Workflow Studio](#workflow-studio)
  - [Trigger Configuration](#workflow-triggers)
  - [Workflow Status Bar (Global Background Execution)](#workflow-status-bar)
  - [Node-level Progress & Interrupt Recovery (Beta)](#workflow-progress-recovery)
  - [Persistent vs. Temporary Workflows](#workflow-persistent-vs-temporary)
  - [Built-in Workflow Templates](#workflow-builtins)
  - [Project Initialization Workflows](#workflow-project-init)
  - [Workflow Agent (Write Workflows in Natural Language)](#workflow-agent)
  - [Workflow Usage Example (Book-Breakdown Workflow)](#workflow-examples)

### Collaboration & Planning

- [Contributing Guide](./CONTRIBUTING.md)
- [Roadmap](./ROADMAP.md)

---

<a id="core-features"></a>
## ✨ Core Features

*   **📚 Schema-driven card creation**
    *   Each card type can define a structure (Schema). AI generation is validated against that structure, reducing "looks usable but falls apart in practice" output.

*   **⚡ Instruction-streaming AI card generation**
    *   No longer "generate the whole thing in one shot." Now it's "enter requirements → stream-fill at the field level → you confirm or give feedback to continue." More controllable, easier to correct, and a smoother generation process that avoids long waits for results.
    *   This capability focuses on generating and refining "the current card"; closing the dialog ends that session.

*   **📝 Chapter body word-count control**
    *   Chapter continuation supports two modes: `Prompt Constraint` and `Control Mode`.
    *   `Prompt Constraint` is more natural and cheaper; `Control Mode` splits the target word count into multiple rounds with budgets — more stable control, but consumes more tokens.

*   **✅ Unified review & review-result cards**
    *   Review follows a unified "draft preview → confirm and save as review-result card" flow.
    *   Different card types can use different review prompts, but the result card structure stays consistent, making viewing and referencing easy.

*   **🧠 Context injection + knowledge-graph consistency**
    *   Precisely reference project data with `@DSL`; combine the relationship graph and dynamic information so subsequent generation stays close to what's already written and character relationships.

*   **🔮 Inspiration Assistant (Agent)**
    *   Sustained conversation, card referencing, and tool calls to modify content. Refine your settings like working with a partner, instead of regenerating whole cards over and over.

*   **🧩 Code-style workflow system**
    *   Refactored onto a code-style workflow mainline (the old DAG approach was removed). Supports visual editing, trigger-based execution, and reuse — ideal for automating common creation tasks.

*   **🤖 Workflow Agent**
    *   Describe your needs in natural language and let the Agent write/modify workflow code, validate it, and apply changes for you.

*   **💡 Ideas Workbench**
    *   Supports free cards, cross-project references, and moving/copying back into a formal project — ideal for dedicated brainstorming and material collection.

---

<a id="changelog"></a>

## 📅 Changelog
<details>
<summary>v0.9.6</summary>

- Optimized prompts
- Several feature improvements
  - **LLM config page capability detection**
    - Trigger model capability/compatibility tests from the LLM config page to help judge support for basic chat, streaming, structured output, tool calling, etc.

  - **Inspiration Assistant batch body-edit suggestions**
    - The Inspiration Assistant can return multiple body-edit suggestions at once; the editor supports reviewing, accepting, or rejecting them one by one.
    - Retained tool-result handling and text-format fallback parsing to reduce failures when the model returns unstable formats.

  - **Task-completion notifications**
    - After an assistant reply or edit-suggestion generation finishes, a sound and desktop notification can be triggered (off by default; toggle in Assistant settings).
- Bug fixes

</details>

<details>
<summary>v0.9.5</summary>

- Fixed workflow bugs
- Changed the book-breakdown workflow to default instruction-stream mode for higher success rate
- Fixed UI display issues on certain resolutions
</details>

<details>
<summary>v0.9.4</summary>

- **Memory-layer information enhancement (Character/Relationship/Scene/Organization/Item/Concept)**
  - Unified extraction preview / confirm-write flow
    In the chapter editor, the following capabilities are unified into a "preview first, then confirm" flow:

    - Character dynamic information
    - Relationship extraction into the graph
    - Scene state
    - Organization state
    - Item state
    - Concept mastery
  - Unified interaction:
    - Initiate extraction based on the current chapter body
    - Show preview results first
    - Allow manual adjustments in the preview
    - Write back to the card or graph only after confirmation
  - This release adds and rounds out lightweight state / memory capabilities for the following entity types (use as needed; not everything must be used, to avoid increasing context complexity):
    - Scene card
    - Organization card
    - Item card
    - Concept card
- Optimized mobile CSS layout; added a show/hide toggle for the bottom-left navigation

- Other optimizations and several bug fixes

</details>

<details>
<summary>v0.9.3</summary>

- **Chapter body word-count control refactor**
  - Chapter continuation word-count control is consolidated into two modes:
    - `Prompt Constraint`: only constrains word count at the prompt level; text is more natural, suitable for cases without strict word-count requirements
    - `Control Mode`: splits the target word count into multiple rounds with budgets; more stable control, but consumes more tokens
  - Control Mode currently uses a fixed multi-round budget strategy, improving stability and controllability for long-chapter continuation

- **Review feature refactor**
  - The review flow is unified into "generate a review draft first, then confirm to create/update the review-result card"
  - Review results no longer depend on the old record model; they are uniformly stored as `Content Review Cards`
  - Review-result cards are auto-filed under the root-level `Review Results` folder for centralized viewing and reuse
  - The review entry in the chapter body and the generic card editor is unified as "review button + prompt switch"

- **Other optimizations**
  - Optimized LLM config, Responses-mode compatibility (Inspiration Assistant still incompatible), export ordering, chapter editor, and several UI details
  - Fixed several bugs, improving overall stability

</details>

<details>
<summary>v0.9.2</summary>

- Added chapter review, stage review, and review-history viewing
  - Click the review button at the top of a stage/chapter body card; the review result pops up when finished.
  - Review history can be viewed in the right panel.
- Added card search, folder-type cards, and one-click front+back startup; fixed a tree-structure fold-state saving issue.
- Automatically checks for differences between model metadata and existing DB table structure, and adds back "safely addable" missing columns.
- Other optimizations

</details>

<details>
<summary>v0.9.1</summary>

- **Relationship graph supports SQLite storage**
  - Added SQLite support for relationship-graph storage (and remains compatible with Neo4j)
  - Added relationship-graph management: filtering, batch editing, import/export, etc.

- **Optimized chapter-body generation and polishing prompts**
  - Improved performance of "content generation/polishing/expansion" prompts, raising output stability and usability
  - Split style-constraint content into knowledge-base injection for independent maintenance and quick adjustment

- **Added accept/reject after chapter-body polish/modify**
  - Polish-replace supports "accept and replace / reject and restore" to reduce mis-replacement risk
- Added copy-LLM-config feature: quickly copy and fine-tune from an existing config, reducing repetitive setup
- Fixed several bugs, improving overall stability and interaction experience

</details>

<details>
<summary>v0.9.0</summary>

- 🚀 **Major update: 0.9.0**

- ✨ **Refactored AI card generation flow**
  - Upgraded from "click and wait for the whole result" to "enter requirements → field-level generation in the dialog → confirm/feedback to continue," significantly improving usability and smoothness~
  - The generation process is more controllable, with lower correction cost.

- 🧱 **Workflow system refactor (exploratory)**
  - We exploratorily migrated workflows from the old **DAG-style editor** to the new **code-style workflow (Python-style statements + special marker DSL)**, and gradually removed the old DAG approach.
  - This is primarily a trade-off between maintainability and AI-friendliness.
  - **Advantages of code-style workflows (current experience):**
    - Logic is more linear and clear: sequence, wait (`Logic.Wait`), async (`async=true`) and other semantics are closer to the real execution process.
    - Progress handling and async operations are more natural: the executor schedules by statement plan, without weaving around a graph.
    - More AI-friendly: the same feature often takes only dozens of lines in code form, while DAG config frequently needs hundreds of lines of node and connection descriptions.
  - **Disadvantages of code-style workflows (needs ongoing polish):**
    - Less intuitive than DAG
    - More sensitive to string/code formatting: parameter serialization, dict field types, variable references and other details are more likely to trigger validation or runtime errors, requiring stronger validation and prompt constraints.

- 🤖 **Added Workflow Agent**
  - Describe your goal in natural language; the Agent generates/modifies workflow code and validates it.
  - Supports a "preview before apply" safe-change experience.
  - May still have some bugs.

- 📚 **Built-in workflow enhancements**
  - Added practical templates like the "Book-Breakdown Workflow" for out-of-the-box use and further customization.

- 🎨 **Inspiration Assistant UI and interaction optimization**
  - Improved conversation rendering, input-area interaction, and tool-call display.

- 🧹 **Engineering refactor and stability improvements**
  - Major restructuring of front/back-end directory structure and module boundaries; improved code maintainability.
  - Fixed a batch of workflow, visual-parameter-editing, and Agent-interaction issues.

- ⚠️ Because this version involves large changes, older databases may not work directly. Try the published migration script (success not guaranteed; back up your DB file beforehand!)

</details>

<details>
<summary>v0.8.6</summary>

- Added version-update detection, auto-checking by default (a red dot appears in Settings → About when a new version is available)
- Optimized the LLM config UI; added a fetch-available-models feature
- Added web-version adaptation
- Code optimization and bug fixes

</details>

<details>
<summary>v0.8.5</summary>

- Fully replaced the agent framework with a new one; optimized the Inspiration Assistant and its UI
- Added Inspiration-Assistant-related settings
- Reimplemented React mode for text-format tool calling for models with weak tool-calling ability. Can be enabled in Settings → Inspiration Assistant (off by default)
- Made reasoning models compatible; added thinking mode
- Recommend choosing/modifying the provider to "OpenAI compatible" for models like DeepSeek and Qwen, while keeping OpenAI set to official models like GPT-5 only.
- Several other optimizations
- Code optimization and bug fixes

</details>

<details>
<summary>v0.8.3</summary>

- Inspiration Assistant enhancements
  - Added ReAct mode: compatible with more LLMs (text-format tool calling); switch between standard/ReAct modes in settings
    (Note: due to time constraints, the ReAct implementation is rough and may have bugs; still recommended to prefer models with good native tool-calling support)
  - Smarter context: tool return values now include parent-card info, so the AI understands card hierarchy more accurately

- UI and experience improvements
  - Referenced-card area rebuilt: fixed layout, always-visible `...(N)` button, using Popover instead of Modal
  - Improved tool-call result display: shows success/failure status, supports jumping to card, collapsible full JSON view
  - Fixed overlap between referenced cards and model selection; adjusted input-box height
- Code optimization and bug fixes

</details>

<details>

<summary>v0.8.2</summary>

- Optimized Inspiration Assistant tool calls; added auto-retry. Max retries configurable via .env
- Enhanced card drag-and-drop; free ordering
- Optimized Inspiration Assistant UI; supports markdown display
- Bug fixes and code cleanup

</details>

<details>

<summary>v0.8.0</summary>

- Chapter editor refactor
  - Migrated from a separate window to the middle column of the main editor, unifying the editing experience
  - Added right-click quick edit: select text, right-click, and enter a request to polish/expand
  - Improved context assembly: polish/expand auto-includes context for more natural continuity
  - Dynamic highlighting of AI-generated content

- Inspiration Assistant enhancements
  - Added tool-calling capability (experimental): create/modify cards directly in the conversation; supports searching and viewing type structures
  - Conversation history management: stores conversation history per project; supports adding/loading/deleting sessions
  - Real-time tool-call feedback: shows "calling tool..." and auto-refreshes the card tree when done
  - Improved context building: auto-injects the project structure tree, statistics, and operation history

- Workflow system optimization
  - Node auto-registration: adding a node takes only a decorator line; the front end syncs automatically
  - Dynamic node library: node list is loaded dynamically from the back end; zero-config extension

- UI and experience improvements
  - Fixed several display issues in dark mode
  - Optimized card editor layout and interaction details
  - Improved visual feedback for streaming output

Note: if you previously chose local development, this version requires reinstalling the back-end requirements

</details>

<details>

<summary>v0.7.8</summary>

- Workflow system (experimental) continues
  - Added "trigger on project creation (onprojectcreate)", replacing old project templates with workflows
  - Canvas interaction improvements: drag to create nodes, delete connections, more accurate coordinate placement
  - Several usability improvements to the Workflow Studio and node-parameter panel
  - Note: workflows remain experimental; currently mainly used to gradually replace hardcoded logic, with much room to extend new capabilities

- Code optimization
  - Cleaned up old project-template-related code and UI, unified into the workflow system

</details>

<details>

<summary>v0.7.7</summary>

- Optimized the Work Tags card
  - Added tag items and option data
  - Split tag-category data out into knowledge-base file storage; edit Work Tags in Settings → Knowledge Base and freely modify tag categories
- Added interrupt capability for card AI generation
- Code optimization and bug fixes; configurable via .env whether to reset knowledge base, prompts, etc. on startup

</details>

<details>

<summary>v0.7.6</summary>

- Enhanced LLM management
  - LLM config supports "Test Connection"
  - Supports usage settings: set token limits, call-count limits (-1 = unlimited)
  - List shows "used (input/output/calls)" and provides "one-click reset statistics." (Current token-usage stats are approximate; different models may count differently; for reference only)

- Code and experience optimizations

</details>

<details>
<summary>v0.7.5</summary>

- Improved: Inspiration Assistant
  - Supports freely referencing multiple card data (cross-project, with dedup and source marking)
  - Can select an LLM model in conversation (overrides card config)
  - Conversation history saved and restored per project; not lost on reload
  - Several UI and interaction refinements

- Initial: Workflow (experimental)
  - Added "Workflow Studio": canvas (Vue Flow), parameter sidebar, node library, and basic trigger CRUD
  - Run & events: supports SSE; `run_completed` carries `affected_card_ids`; front end refreshes at card granularity
  - Important note: currently experimental; UI interaction/DSL/validation/Runner/triggers are still being refined

</details>

<details>
<summary>v0.7.0</summary>

- New: Inspiration Assistant
  - A conversational collaboration tool in the right panel, supporting real-time discussion and iterative refinement of card content.
  - Cross-project card referencing to inject any project's card data into the conversation and spark creative collisions.
  - Auto-references the currently selected card for seamless context switching.
  - One-click "finalize" to apply conversation results directly to card content.
  - Reset-conversation feature for starting fresh creative discussions.

- New: Ideas Workbench
  - A separate-window mode providing a focused creative-exploration environment.
  - A free-card system unconstrained by project structure.
  - Cross-project referencing and creative fusion.
  - One-click move/copy of free cards into a formal project.

- Improved: Import cards
  - Upgraded "import free card" to "import card", supporting import from any project.
  - Improved card selector, grouped by type with collapse/expand support.
  - Optimized reference-data caching for better performance and responsiveness.

</details>

<details>
<summary>v0.6.5</summary>

- New: Project Templates — migrated to the workflow system in v0.7.8
  - Settings page adds "Project Templates" management; configure the card types and order auto-created on new project creation, forming a reusable creation pipeline; multiple templates can be maintained.
  - New project supports selecting a template.
  - Back end adds template data model and CRUD API; the app writes default project templates on startup.

</details>

---

<a id="tech-stack"></a>
## 🛠️ Tech Stack

*   **Frontend:** Electron, Vue 3, TypeScript, Pinia, Element Plus
*   **Backend:** FastAPI, SQLModel (Pydantic + SQLAlchemy), Uvicorn
*   **Database:** SQLite (core data), Neo4j (knowledge graph)

---

<a id="getting-started"></a>
## 🚀 Getting Started

Whether you want to try it directly or get involved in development, it's easy to start.

### 0. Neo4j Desktop (optional, not required)

The project now uses SQLite by default to implement relationship-graph storage, but you can also switch to Neo4j. Steps:

*   Download and install **Neo4j Desktop**, recommended version **5.16** or higher.
*   Download link: [Neo4j Desktop](https://neo4j.com/download/)
*   After installing, create a local database instance and make sure it is **running**. Default connection info can be configured in the `.env` file.
![alt text](docImgs/README/image-6.png)

### Option 1: Run from source (developer / latest features) (non-developers should use Option 2)

**1. Backend (Python / FastAPI)**
```bash
# Clone the repo
git clone https://github.com/nolepguy/NovelForge-EN.git
cd NovelForge-EN/backend

conda create -n NovelForge python=3.11
conda activate NovelForge

# Install dependencies
pip install -r requirements.txt

Rename backend/.env.example to .env

# Run the backend service
python main.py
```

**2. Frontend (Node.js / Electron)**
```bash
# Enter the frontend directory
cd ../frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
# You can also start the web page with the following command
// npm run dev:web
```

**3. One command to start both front and back end (npm)**
```bash
npm run dev
```

#### Important: BOOTSTRAP_OVERWRITE in .env

> When starting the backend, the system initializes/updates built-in resources (knowledge base, prompts, workflows, etc.) as needed. Whether to overwrite is controlled by `BOOTSTRAP_OVERWRITE` in `.env`.

- Recommended settings:
  - If you have not directly modified built-in resources, it is recommended to set:
    ```ini
    BOOTSTRAP_OVERWRITE=true
    ```
    This auto-syncs the latest built-in knowledge base/prompts/workflows on version upgrade or restart.
  - If you have directly modified "built-in" resources, it is recommended to set it to `false` to avoid being overwritten.

- Recommendations (to avoid being overwritten):
  - Do not directly edit "built-in" resources.
  - For customization, create a copy (copy the knowledge base/prompt/workflow and rename it) and edit the copy. This way, even if `BOOTSTRAP_OVERWRITE=true` later, your custom copy will not be overwritten by the update logic.


### Option 2: Use a release (quick start)

Releases are packaged periodically; no dev environment needed, ready to use.

1.  Go to the project's **Releases** page and download the latest portable archive (`.zip` or `.7z`).
2.  Extract to any location.
3.  **(Important)** Before running, ensure the database instance in Neo4j Desktop is started.
4.  Enter the extracted folder, find the `backend` directory, and edit the `.env` file to configure the database connection as needed.
5.  Run `backend/NovelForgeBackend.exe` to start the backend service.
6.  Go back one level and run `NovelForge.exe` to start the main program.

> Most data is stored in the backend/novelforge.db database. When updating/migrating versions, just copy that DB file to the corresponding location.
---

## ✍️ Creation Workflow

1.  **Configure the LLM**
    *   After first launch, add your AI model config in Settings, such as API Key, Base URL, etc.
    ![alt text](docImgs/README/image.png)
    Recommend using an LLM at the Gemini 2.5 Pro level or above for creation.

2.  **Create a project and initialize the workflow**
    *   When creating a new project, you can choose an initialization workflow (usually `onprojectcreate` type) to auto-create preset cards. The system has a built-in "Project Creation · Snowflake Method" workflow that auto-creates a complete card tree following the snowflake method.
    ![alt text](docImgs/README/image-1.png)

3.  **Top-down, fill in core settings**
    *   Progress from the top-level card (one-line pitch → story outline → worldview → core blueprint).
    *   Each card can open the AI generation dialog, enter this round's requirements, and the system streams generation at the field level.
    *   After generation, you can "confirm" to commit directly, or submit feedback to keep iterating — no need to redo the whole card if unsatisfied.
    After finishing the Core Blueprint card and clicking save, volume cards are auto-created based on the volume count.
    Then continue with the volume-outline creation, starting from Volume 1.
    Once done, stage-outline sub-cards and a writing-guide card are auto-created based on the stage count. It is recommended to generate the writing-guide card first to produce writing guidance, then proceed with stage-outline creation.
    ![alt text](docImgs/README/image-2.png)
    AI card-generation example flow:
    ![alt text](docImgs/README/image-28.png)
    ![alt text](docImgs/README/image-29.png)
    When done, click finish, then save the card. Or, if unsatisfied with certain fields, enter guidance as feedback.

4.  **Refine content with the Inspiration Assistant**
    *   While writing, if you want to further polish or optimize card content, you can use the Inspiration Assistant on the right at any time.
    *   After selecting any card, the Inspiration Assistant auto-reads that card's content for easy reference and thinking.
    *   You can directly ask the assistant specific questions, such as "Is this character's motivation reasonable?" or "How can I make this scene more tense?"
    *   The Inspiration Assistant gives targeted suggestions based on the current card content, and you can go back and forth with the assistant to gradually refine ideas.
    *   Via the "Add Reference" button, you can also pull in related cards from this or other projects to spark more creativity.
    *   The Inspiration Assistant is context-aware and can use tools to modify/create card content (experimental).
    ![Alt text](docImgs/README/image-20.png)

#### AI Generation Dialog vs. Inspiration Assistant (how to choose)

- **AI Generation Dialog**: focuses on the current single card, for quickly generating and iterating that card's content; the session lasts only until this generation flow ends and clears when the dialog is closed.
- **Inspiration Assistant**: for sustained cross-card, cross-project conversation and creation; can reference multiple cards for analysis and linked creation, with persistently saved conversation history.
- **Suggested usage**:
  - Goal is "write this one card well" → use the AI Generation Dialog.
  - Goal is "cross-setting linked thinking / long-term discussion / multi-card collaboration" → use the Inspiration Assistant.

5.  **After finishing the stage outline, chapter outlines and chapter-body cards are auto-generated, and the entities each chapter needs are auto-injected.**
    ![alt text](docImgs/README/image-3.png)

6.  **Enter chapter writing**
    *   After the above steps, click the corresponding chapter-body card to open the chapter editor and enter the core writing interface. The right-side context panel auto-prepares all background material needed for the current chapter.
    ![Alt text](docImgs/README/image-27.png)

    *    Click continue-writing for AI generation (if there is no content, it starts writing from scratch).
    *    When continuing, you can choose two word-count control modes:
         - **Prompt Constraint**: only constrains word count at the prompt level; text is more natural and saves tokens.
         - **Control Mode**: splits the target word count into multiple rounds with budgets, suitable when you need stricter control over the chapter's total word count, but consumes more tokens.
    *    If unsatisfied with the generated content, select it, right-click for quick edit, enter a request, and click polish/expand to rewrite that part.
    ![Alt text](docImgs/README/image-8.png)

    *    The chapter body also supports direct review:
         - Click the **Review** button at the top to run a review
         - Switch review prompts via the dropdown to the right of the button
         - The review returns a draft first, then is saved as a review-result card after confirmation
         - Saved results are auto-placed in the root-level **Review Results** folder and can be viewed in the right panel

    *   When content creation is done, click extract-to-graph to parse character relationships and store them in the knowledge graph for reference during later writing.
    ![Alt text](docImgs/README/image-7.png)
    After extraction, click confirm to save into the Neo4j database.
    ![alt text](docImgs/README/image-5.png)

    *    It is recommended to also extract character dynamic information, which can use a cheaper model.


    *    After the above steps, when creating the next chapter, relevant participating entity info is auto-injected.
    ![alt text](docImgs/README/image-9.png)

7.  **Ideas Workbench: capture creative sparks**
    *   Got a new idea but not sure which project it belongs to? Click the "Ideas" button at the top to open the standalone Ideas Workbench window.
    *   Here you can jot down thoughts and freely create cards of various types without worrying about project structure, focusing on capturing inspiration.
    *   The Inspiration Assistant on the right supports referencing any project's card content, making it easy to look up, compare, and combine across projects for more inspiration.
    *   When an idea takes shape, use the "Move/Copy to Project" feature at the top to one-click file the free card into a formal project, naturally connecting it to subsequent creation.
    ![Alt text](docImgs/README/image-21.png)
    ![Alt text](docImgs/README/image-22.png)
---

## ⚙️ Advanced Features & Configuration

While NovelForge provides a recommended creation workflow, its real power lies in its high flexibility. You can discard the presets entirely and use the following tools to compose your own creation system.

<a id="schema-first"></a>
### Schema-first: Type/Instance Structure & Parameters

*   In `Settings → Card Types`, use the structure builder to define a `json_schema` for a type (supports basic types, relation(embed), tuple, etc.). The type Schema serves as the default structure for that type's cards.
    ![alt text](docImgs/README/image-10.png)
    ![alt text](docImgs/README/image-11.png)

*   In a specific card, you can open `Structure` (Schema Studio) to override that card instance's structure, or one-click "apply to type."
    ![alt text](docImgs/README/image-12.png)

    ![alt text](docImgs/README/image-13.png)

    After applying to type, subsequently created cards of that type will use the new structure.

*   Card AI parameters: set model, prompt, temperature and other params via the editor toolbar (`llm_config_id`, `prompt_name`, `temperature`, `max_tokens`, `timeout`).
    ![alt text](docImgs/README/image-14.png)

*  After the above, you can create cards of that type in the project and run AI generation. The system uses that card's "effective Schema" for structured validation and output.
    ![alt text](docImgs/README/image-15.png)
    When creating a new card, you can also drag from an existing card to below and auto-create it.
    ![alt text](docImgs/README/image-16.png)

    ![alt text](docImgs/README/image-17.png)

*  Schema supports embedding (`$ref` to type `$defs`), so you can compose and reuse existing structures for composite-capability building.

    ![alt text](docImgs/README/image-18.png)

Note: prefer adding new models rather than modifying existing model structures, to avoid conflicting with existing data.

### Chapter Review & Generic Review

Besides the chapter body, other cards (e.g. stage outline, generic text) can also directly use the **Review** button at the top.

- The review entry is unified as a single button, with a prompt switch to its right
- Stage outline defaults to the `Stage Review` prompt
- Regular cards default to the `Generic Review` prompt
- Review results are uniformly saved as `Content Review Cards`

This way you can configure different review standards for different card types while keeping a unified review-result structure and viewing method.


<a id="prompt-workshop"></a>
### Prompt Workshop

*   Behind every AI feature is an editable prompt template. You can modify preset templates here or create brand-new ones.
*   **Knowledge-base injection**: supports dynamically referencing "knowledge base" content in prompts via the `@KB{name=kb-name}` syntax, giving the AI richer background information.

<a id="context-dsl"></a>
### Context Injection (@DSL) in Depth

This is a NovelForge signature feature. It lets you precisely reference any data in the project within a prompt template using the `@` symbol, injected as context.

*   **By title**: `@CardTitle` or `@CardTitle.content.someField`
*   **By type**: `@type:CharacterCard` (all character cards)
*   **Special references**: `@self` (current card), `@parent` (parent card)
*   **Powerful filters**:
    *   `[previous]`: get the previous sibling card.
    *   `[previous:global:n]`: get the nearest n same-type cards in global order (tree pre-order).
    *   `[sibling]`: get all sibling cards.
    *   `[index=...]`: get by ordinal, supports expressions, e.g. `$self.content.volume_number - 1`.
    *   `[filter:...]`: filter by condition, e.g. `[filter:content.level > 5]` or `[filter:content.name in $self.content.entity_list]`.
*   **Field-level selection**: you can select the entire card data or just a specific card field.

For example, referencing the titles and body of the nearest 3 chapters:
![Alt text](docImgs/README/image-23.png)

<a id="workflow-system"></a>
### Workflow System (Code-style Workflows + Workflow Agent)

The workflow system orchestrates common creation actions (project initialization, auto-generating sub-cards on save, batch content processing, etc.) into reusable flows that run automatically at the right time.

The code-style mainline refactor is complete; the old DAG-style workflow approach has been removed.

<a id="workflow-studio"></a>
#### Workflow System

- Visit the "Workflow" page to edit workflows in both visual and code views.
- Quickly build a flow via the node library, or directly write/modify code.
- The parameter panel supports real-time editing and validation; changes can be safely applied to the workflow code.
- View run records, execution results, and error info for easier iterative debugging.

![alt text](docImgs/README/image-30.png)

<a id="workflow-triggers"></a>
#### Trigger Configuration

Each workflow can be configured with one or more triggers defining when it auto-executes:

- **Trigger on save**: auto-executes when a specified type of card is saved
- **Trigger on project creation**: auto-executes after a new project is created (commonly used for project initialization)


<a id="workflow-status-bar"></a>
#### Workflow Status Bar (Global Background Execution)

- After a workflow runs, its status shows in the global workflow status bar (not limited to the workflow page).
- You can switch to other pages and keep creating; the workflow runs in the background.
- The status bar shows the number running, the current node, overall progress, and completion state.

![alt text](docImgs/README/image-25.png)

<a id="workflow-progress-recovery"></a>
#### Node-level Progress & Interrupt Recovery (Beta)

- The system supports node-level progress reporting, so you can see "which node it's currently executing."
- Supports pause/resume execution, retaining run state for re-running.
- Supports run-record persistence and viewing.
- Note: this capability is usable; complex flows may have a few edge issues (e.g. certain recovery scenarios).

<a id="workflow-persistent-vs-temporary"></a>
#### Persistent vs. Temporary Workflows

- **Temporary workflow (default)**: run records are for current viewing and debugging, and are auto-cleaned up later.
- **Persistent workflow**: after enabling "persist saves," run records are retained long-term (subject to the system retention policy).


<a id="workflow-builtins"></a>
#### Built-in Workflow Templates

The system ships with several common workflows, ready to use or as references:

- **Project Creation · Snowflake Method**: auto-creates the initial card structure following the snowflake method on new project creation
- **Worldview → Organization**: auto-generates organization cards from the worldview's faction list
- **Core Blueprint → Seed Cards**: auto-creates character cards, scene cards, and volume cards based on the blueprint content
- **Volume Outline → Seed Cards**: auto-creates stage outlines and writing guides based on the volume outline
- **Stage Outline → Chapter Cards**: auto-creates chapter outlines and body cards based on the stage outline's chapter list
- **Book-Breakdown Workflow**: for breaking down an existing text's structure and landing it into the card system

<a id="workflow-project-init"></a>
#### Project Initialization Workflows

When creating a new project, you can choose an `onprojectcreate`-trigger workflow as a project template:

- Defaults to "Project Creation · Snowflake Method," which auto-creates Work Tags, Special Ability, One-line Pitch, Story Outline, Worldview Setting, Core Blueprint, etc.
- You can also create your own project-init workflow in the Workflow Studio to fully customize the project's starting structure
- Supports complex initialization logic, such as creating different card structures based on conditions

![Alt text](docImgs/README/image-26.png)

<a id="workflow-agent"></a>
#### Workflow Agent (Write Workflows in Natural Language)

- On the workflow page, open the Workflow Agent and tell it your goal, e.g. "Create a multi-AI debate flow and output it to a specified project."
- The Agent auto-reads the current workflow, generates a modification plan, validates it, and gives an applicable result.
- This way, you don't need to build the workflow yourself; you can quickly implement complex flows.
- May still have some bugs.

![alt text](docImgs/README/image-31.png)
![alt text](docImgs/README/image-32.png)
![alt text](docImgs/README/image-33.png)
![alt text](docImgs/README/image-34.png)
![alt text](docImgs/README/image-35.png)
(The right-side execution panel shows detailed progress; the workflow status bar is a simple progress display.)
For long-running tasks, you can switch to other views instead of waiting on the workflow page. When done, the workflow status bar flashes to notify you.

<a id="workflow-examples"></a>
#### Workflow Usage Example
Book-Breakdown Workflow
First create an empty project
![alt text](docImgs/README/image-36.png)

Go to the workflow page and select the book-breakdown workflow

![alt text](docImgs/README/image-37.png)

Set the target project, model name, and novel chapter directory

![alt text](docImgs/README/image-38.png)

Note: novel files must be stored in a preset format, e.g. split into txt files per chapter
![alt text](docImgs/README/image-41.png)

Click execute to run it


Breakdown result:
![alt text](docImgs/README/image-39.png)

Extract chapter outline → divide stage storylines → run a global analysis based on all stage storylines

---

## License
This project uses a dual-license model:

- By default, this project is licensed under the GNU Affero General Public License v3.0 (AGPLv3).
- Service-type commercial use: providing this project (or its modified version) as a backend to third parties as SaaS, hosting, or other forms requires obtaining a commercial license from the author.

Please comply with the open-source license terms and obtain the corresponding authorization where applicable.

---

<a id="project-structure"></a>
## 📂 Project Structure

```
NovelForge/
  ├── backend/        # FastAPI backend
  │   ├── app/
  │   │   ├── api/        # API routes
  │   │   ├── db/         # DB models and sessions
  │   │   ├── schemas/    # Pydantic data models
  │   │   └── services/   # Core business logic
  │   └── main.py       # Entry point
  │
  └── frontend/       # Electron + Vue3 frontend
      └── src/
          ├── main/       # Electron main process
          ├── preload/    # Preload scripts
          └── renderer/   # Vue renderer process
              └── src/
                  ├── components/ # Vue components
                  ├── services/   # Frontend services
                  ├── stores/     # Pinia state management
                  └── views/      # Page views
```

---

<a id="outlook"></a>
## Outlook

NovelForge is still in an early iteration stage. The author is well aware there is huge room for improvement in creation workflow, consistency maintenance, UI design, interaction experience, and more.

The best tools come from community wisdom. Whether you are a creator or a developer, you are sincerely welcome to:

*   Raise valuable feature suggestions or report issues in **Issues**.
*   Share your unique insights on the creation workflow.
