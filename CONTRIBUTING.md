# Contributing Guide

First, thank you for wanting to contribute to NovelForge ❤️

Whether fixing a small issue or pushing a big feature, you are very welcome. To make collaboration smoother and reviews more efficient, please follow the conventions below.

## 1. Small Features / Bug Fixes: Submit a PR Directly

Applies to:

- Small-scope feature enhancements
- Bug fixes
- Copy and interaction improvements
- Small refactors (that don't change core architecture)

When submitting a PR, please include:

1. **Change summary**: one sentence on what changed and what problem it solves.
2. **File-level notes**: list the main files changed and the purpose of each change.
3. **How to verify**: how you verified the change works (manual steps, key logs, test results).

Suggested format (can be copied into the PR description):

```markdown
## Change Summary
- 

## File Changes
- `path/to/fileA`:
- `path/to/fileB`:

## Verification
- 
```

## 2. Big Features: Open an Issue to Discuss First, Then Implement

If you plan to contribute a larger feature (e.g. architecture changes, core-flow rework, large cross-front/back-end changes), please open an Issue first to discuss with the author/maintainers before developing.

The Issue should include:

- Background and problem
- Goals and scope (what to do / what not to do)
- Solution sketch (key design points)
- Impact on existing behavior

This avoids rework and helps you get effective feedback faster.

### Suggested Issue Title Format

To make it easy to distinguish from normal bug reports, use the following title format:

- **Big-feature proposal (recommended)**: `[Proposal][Module] one-line goal`
- **Claim a planned feature (recommended)**: `[Claim][Module] feature to implement`
- **Small fix (optional)**: `[Fix][Module] problem summary`

Examples:

- `[Proposal][Workflow] Add parallel-branch error-recovery strategy`
- `[Claim][Agent] Implement batch example templates for the Workflow Agent`
- `[Fix][Editor] Fix chapter-body autosave conflict`

Notes:

- `[Proposal]` is for discussing an approach before development;
- `[Claim]` is for "I'm planning to do this," reducing duplicate work;
- After the feature is done and the PR is merged, please close the corresponding Issue.

## 3. Development Standards: Follow the Project Rules

Please follow the project engineering rules when developing:

- `rules/novelforge-engineering-rule.md`

The core requirements can be summarized as:

- Clear design, avoid coupling and hardcoding
- Clean code, prioritize maintainability
- Changes have a validation loop; no "looks like it runs" fragile implementations

## 4. Code Style & Collaboration Tips

- Try to keep "small focused commits"; avoid mixing too many unrelated changes into one PR.
- Don't opportunistically rewrite unrelated modules (unless agreed in an Issue).
- Prioritize adding or updating necessary docs so later maintainers can quickly understand your changes.

## 5. Communication

If you're unsure whether a design is appropriate, feel free to open an Issue first or clearly write out your trade-offs and questions in the PR.

Thanks again for your contribution!
