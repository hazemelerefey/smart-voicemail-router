![SVR System, Smart Voicemail Router](assets/svr-readme-banner.png)

<p align="center">
  <a href="docs/project/PRD.md"><img src="https://img.shields.io/static/v1?label=PRD&amp;message=v1.2&amp;color=2a9d8f&amp;style=for-the-badge&amp;logo=readthedocs&amp;logoColor=white" alt="PRD v1.2"></a>
  <a href="docs/project/architecture.md"><img src="https://img.shields.io/static/v1?label=Architecture&amp;message=v1.2&amp;color=4169e1&amp;style=for-the-badge&amp;logo=mermaid&amp;logoColor=white" alt="Architecture v1.2"></a>
  <a href="docs/project/team-allocation.md"><img src="https://img.shields.io/static/v1?label=Team%20Plan&amp;message=v1.2&amp;color=d08c34&amp;style=for-the-badge&amp;logo=git&amp;logoColor=white" alt="Team plan v1.2"></a>
  <a href="SETUP.md"><img src="https://img.shields.io/static/v1?label=Setup%20Guide&amp;message=Local%20and%20optional%20GPU&amp;color=7952b3&amp;style=for-the-badge&amp;logo=bookstack&amp;logoColor=white" alt="Setup guide"></a>
</p>

# Smart Voicemail Router

A local-first competition prototype designed to turn a single-speaker Egyptian Arabic voicemail, including English telecom terms, into an explainable callback ticket.

> **Project status:** The approved v1.2 documents are drafts for team review. Dataset taxonomy and the evaluation protocol are pending shared EDA. This setup draft contains documentation and environment guidance only. It does not include application code, a dataset, model weights, or measured results.

## Project intent

The proposed workflow accepts a voicemail, keeps the original recording within the approved local data boundary by default, and produces a transcript, callback brief, separate complaint and customer context fields, an explainable queue decision, and an agent-routing reason. Audio-derived customer-state evidence is conditional on validation. The prototype is not a production telecom system and does not make automatic callbacks.

The core fields are deliberately distinct:

- **Complaint category** describes the kind of issue.
- **Complaint urgency** describes how time-sensitive or impact-heavy the issue is.
- **Customer state** describes the customer's interaction state under definitions agreed by the team.
- **Queue priority** is a separate system decision based on approved signals.

Final label values, annotation rules, and priority weights are not fixed until the team reviews the authorized dataset and approves a shared specification. Unclear or unsupported outputs should remain reviewable rather than being guessed.

## Data boundary

The v1.2 design keeps raw voice local by default. A transcript approval does not authorize audio transfer. Any permitted external text experiment requires prior, durable approval for the exact provider, purpose, and payload, with local identifier masking first. Dataset source, rights, consent, retention, and allowed processing locations still need to be confirmed before any data is used. No recordings or transcripts are included here.

The `.gitignore` excludes dataset directories at any depth and common dataset export formats by default. Ignore rules are a safeguard, not permission to use or share data. Never force-add private recordings or transcripts. Only reviewed, approved derived summaries may be considered for a later commit, after the team confirms that the specific content and processing are permitted.

## Draft repository structure

```text
.
├── .gitignore
├── README.md
├── SETUP.md
├── CONTRIBUTING.md
├── assets/
│   ├── svr-readme-banner.png
│   └── svr-readme-banner.svg
├── CPU case/
│   ├── README.md
│   └── requirements.txt
├── GPU case/
│   ├── README.md
│   └── requirements.txt
├── Google Colab/
│   └── README.md
└── docs/
    ├── AI_AGENT_GUIDE.md and AI_AGENT_GUIDE.pdf
    ├── project/
    │   ├── PRD.md and PRD.pdf
    │   ├── architecture.md and architecture.pdf
    │   ├── team-allocation.md and team-allocation.pdf
    │   └── architecture-overview.mmd and architecture-overview.png
    └── research/
        └── repository-design-patterns.md
```

This is a documentation and setup skeleton. Application, test, and evaluation directories are intentionally not created in this draft. The architecture and team plan call for fixture-first work and stable shared contracts before integration. Add code and test areas when the team starts those workstreams against an agreed contract.

## Local environments

- [Setup guide](SETUP.md) links the local CPU path, optional GPU path, and optional Colab guidance.
- [CPU case](CPU%20case/README.md) is the reproducible starting point for general tooling and core tests. Tests must not require CUDA.
- [GPU case](GPU%20case/README.md) is optional. CUDA and model-specific libraries are not included in its requirements file.
- [Google Colab](Google%20Colab/README.md) is optional and subject to the same data permissions as local work. Free resources are not guaranteed.

The separate requirements files currently pin only general development tools. The current `pytest==9.2.0` and `mypy==2.4.1` pins require Python 3.10 or later. That tooling minimum does not settle the project-wide Python version, which still needs a team decision. Application and model dependencies remain to be selected. For PyTorch and CUDA, use the [official PyTorch installation selector](https://pytorch.org/get-started/locally/) and defer the exact wheel until the target hardware and model are chosen.

## Pair workstreams and branch plan

The team plan assigns three pair workstreams:

| Pair | Workstream | Planned branch |
|---|---|---|
| Hazem and Ibthal | Audio and speech evidence | `team/audio-speech` |
| Lama and Ahmed | Complaint and customer understanding | `team/complaint-analysis` |
| Sira and Aya | Decision, routing, and evaluation | `team/routing-evaluation` |

The approved team workflow uses `develop` as the integration line and reserves `master` for a final validated result. This local setup-only snapshot intentionally puts the complete setup commit on `master` as a child of a shared empty base. `develop` and the three pair branches point to that empty base. This local branch-content layout does not set or verify GitHub's default branch. Remote setup and default-branch choices remain a later approval gate.

For project work, each pair uses its planned branch and submits reviewable changes. Hazem reviews and merges accepted work into `develop`; only the final validated result is promoted from `develop` to `master`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and review evidence.

## Project documents and guides

The Markdown files are the editable v1.2 project sources. PDF copies and the architecture diagram are included for convenient review.

- [Product Requirements Document, Markdown](docs/project/PRD.md) and [PDF](docs/project/PRD.pdf)
- [Architecture, Markdown](docs/project/architecture.md) and [PDF](docs/project/architecture.pdf)
- [Team Allocation and Delivery Plan, Markdown](docs/project/team-allocation.md) and [PDF](docs/project/team-allocation.pdf)
- [Architecture diagram source](docs/project/architecture-overview.mmd) and [rendered diagram](docs/project/architecture-overview.png)
- [AI Agent Guide, Markdown](docs/AI_AGENT_GUIDE.md) and [PDF](docs/AI_AGENT_GUIDE.pdf)
- [Setup guide](SETUP.md)
- [Repository design patterns research note](docs/research/repository-design-patterns.md)

## Evaluation and claims

The PRD sets evaluation work as a project goal, not a result already achieved. Report only measured results from an authorized dataset and documented split, configuration, runtime, sample counts, and limitations. This draft contains no accuracy or latency result, no dataset-rights determination, and no production-security claim.

## Current open decisions

The approved documents leave dataset access and permissions, label definitions, retention, model and provider selection, the Python baseline, local hardware, the competition deadline, and frontend and deployment ownership open. Resolve those through the project decision process before treating this setup draft as a runnable system.
