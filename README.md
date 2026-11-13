# Smart Voicemail Router

Ready branch. This branch has everything a member needs to clone and start working.

## What is on this branch

- The dataset: SVR Voicemail Corpus, 6,522 voicemails, 5,751 clean training rows, split train 4,031 / validation 1,136 / test 584, seed 42.
- The clean training tables in `final/`.
- The preparation notebooks in `notebooks/`.
- The training skeleton in `notebooks/training/`.
- The latest docs in `docs/`.
- The Phase 1 guides in `docs/project/`.
- The model selection report in `research/`.
- Per-member requirements in `requirements/`.
- `MEMBER.md`.

Arafa's pipeline skeleton is NOT on this branch. It stays on his local machine until he fixes the audit issues, then he pushes it and members pull it.

This branch was renamed from local-env. It is the data branch: the dataset lives on this branch.

## Team

| Member | Role | Branch |
| --- | --- | --- |
| Hazem Elerefy | Training Lead | team/hazem-training-lead |
| Sira | Audio and Speech | team/sira-audio-speech |
| Lama | Text Classification | team/lama-text-classification |
| Aya | ML Infrastructure and Evaluation | team/aya-ml-infrastructure-evaluation |
| Ibthal | Triage and Routing | team/ibthal-triage-routing |
| Arafa | Systems Integration and Demo | team/arafa-systems-demo |

## How to start

1. Clone this branch from VS Code: `git clone -b smart-voicemail-router https://github.com/hazemelerefey/smart-voicemail-router.git`
2. Edit `MEMBER.md` to your own name. Do not commit that change.
3. Create a Python 3.11 virtual environment and install base plus your member requirements file.
4. Verify the counts: train 4,031 / validation 1,136 / test 584.
5. Read `docs/project/roles-and-workflow.md` and start your role's Phase 1 work.

The worktree folder for role branches is still `svr-data`: `git worktree add ../svr-data smart-voicemail-router`.

## Notes

- The taxonomy category count is not settled (9 vs 10 vs 11 vs 12). Hazem confirms the approved list. Do not change any label value.
- Arafa's pipeline skeleton is NOT on this branch. It stays on his local machine while he fixes the audit issues (GitHub issues #1-#9). When the fixes are done he pushes it, and members pull it.
