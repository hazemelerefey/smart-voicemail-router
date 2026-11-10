# Contributing

This guide follows the Smart Voicemail Router v1.2 team plan. The pair branch names and merge flow below are planned repository conventions. This local content draft does not create remote branches, merge work, or add collaborators.

The current local setup-only snapshot places the complete setup commit on `master` as a child of a shared empty base. `develop` and all three pair branches point to that empty base. This temporary local layout does not set or verify the remote default branch; it is separate from the team workflow below, which uses `develop` for integration and reserves `master` for a final validated result.

## Contribution flow

1. Read the current [PRD](docs/project/PRD.md), [architecture](docs/project/architecture.md), and [team allocation](docs/project/team-allocation.md) before starting a task.
2. Work within the pair's assigned area. Keep changes bounded, testable, and reviewable. Use synthetic fixtures for routine work.
3. Do not decide labels, annotation rules, data permissions, retention, provider choices, or shared schema behavior independently. Surface unresolved decisions to the project owner and wait for an approved decision.
4. Run the checks relevant to the change. Report the exact commands, observed results, limitations, and any data-contract or dataset impact with the change.
5. Push progress only to the pair's own branch after repository setup is authorized. Present the change and evidence to Hazem for review. Do not merge it yourself.
6. Hazem validates accepted pair work and merges it into `develop`, the default integration branch. Hazem promotes only the final validated result to `master`.

Use smaller, reviewable contributions. A proposed interface change should include a short written decision and coordinated updates to tests and consuming workstreams. A passing test is evidence about that test, not proof of every product requirement.

## Planned branches

| Branch | Owner or purpose |
|---|---|
| `develop` | Default branch and integration line for accepted pair work |
| `master` | Final line for the validated result |
| `team/audio-speech` | Hazem and Ibthal, audio and speech evidence |
| `team/complaint-analysis` | Lama and Ahmed, complaint and customer understanding |
| `team/routing-evaluation` | Sira and Aya, decision, routing, and evaluation |

Create the three pair branches from the initial commit. Pair members work on their designated pair branch. Hazem is the merge decision owner for accepted pair work and the final promotion. Do not merge directly to `master`. Do not invite collaborators until Hazem supplies and approves their GitHub usernames.

## Data and privacy rules

- Confirm data origin, rights, consent, competition permission, and allowed processing locations before opening or copying any recording.
- Keep raw audio within the approved local boundary by default. Do not upload recordings, transcripts with personal data, or secrets to public notebooks, external AI services, logs, commits, or agent prompts.
- Transcript masking does not anonymize audio. External text processing is opt-in and requires a durable pre-transfer approval matching the exact provider, purpose, and payload. That approval does not authorize audio transfer.
- Keep credentials out of source control. Use approved local environment variables or secret storage.
- Do not add dataset files, recordings, transcripts, checkpoints, or model artifacts to a contribution. Never use `git add -f` or another bypass to add private recordings or transcripts.
- Ignore rules do not grant data permission. Only reviewed, approved derived summaries may be considered for a later commit, after the team confirms that the specific content and processing are permitted.

## Experiments and reporting

For an experiment intended to measure a change, change one experimental factor at a time while holding the dataset snapshot and split, schema, prompt, other configuration, and evaluation procedure constant as far as possible. Record the run ID and hypothesis, changed factor, held-constant conditions, machine and runtime, command, metrics, sample counts, failures, artifacts, and limitations. This rule applies to experimental comparisons, not to every ordinary code edit.

## Review checklist

Before asking for review, make it easy for the reviewer to see:

- The purpose and files changed.
- The commands run and their actual outcomes.
- Any behavior not tested and any known limitations.
- Any contract, label, privacy, dataset, provider, or retention impact.
- Whether the change keeps complaint category, complaint urgency, customer state, voice evidence, and queue priority separate.
