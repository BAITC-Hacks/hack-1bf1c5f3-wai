---
name: start-hackathon
description: Activate HackAlem sprint mode for this repository. Switch origin to the organizer-provided BAITC-Hacks/hack-1bf1c5f3-wai GitHub repository, then keep future commits and pushes for this project there.
---

# Start Hackathon

Use this skill only when the user explicitly activates `$start-hackathon` or clearly says to start the HackAlem sprint. Hackathon-related work before activation stays on the current remote.

## On activation

1. Work from the HackAlem repository root. Check `git rev-parse --show-toplevel`, the current branch, working-tree status, and all configured fetch/push URLs before changing configuration.
2. Set `origin` to `https://github.com/BAITC-Hacks/hack-1bf1c5f3-wai` and verify both its fetch and push URLs. If `origin` does not exist, add it. Leave other named remotes untouched.
3. Use the current team member's own Git identity for new commits. Check the repository-local `user.name` and `user.email`; if either is missing or clearly belongs to a different person, ask that member for the correct identity before committing. Never change global identity or credentials.
4. Report the active branch, verified `origin`, whether there are local changes or commits to publish, and any divergence from `origin`.
5. Do not commit, push, pull, rebase, reset, or force-push merely because the skill was activated. Change only the remote configuration on activation; handle synchronization when the user asks.

## After activation

For this repository, commit and push only through `origin`, which must resolve to `https://github.com/BAITC-Hacks/hack-1bf1c5f3-wai` (accept the same URL with a trailing `.git`). Before every push, verify the push URL. Do not push to another remote, even if another remote is configured. Do not switch back unless the user asks.

Never use force-push or rewrite published history unless the user explicitly requests that operation. If the target branch has diverged or the target repository cannot be verified, stop before publishing and explain the state and safe next options. Never include `.env.local`, API keys, or private challenge data in a commit. Keep `OPENAI_API_KEY` server-side.

Follow the repository's `AGENTS.md` and `docs/team-playbook.md` for task scope, GitHub Issue workflow, integration, hourly progress, deployment, and submission. Keep the judge journey runnable and preserve no-key sample mode.

