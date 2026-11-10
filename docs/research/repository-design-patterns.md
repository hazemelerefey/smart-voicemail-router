# Repository design patterns

**Checked:** 10 November 2026. These are live ranking-page observations, not an archived history. The pages can change after this check.

This note records what the ranking pages displayed, then separately states design judgments for the Smart Voicemail Router draft. A position, star count, gained count, fork count, or contributor count is not evidence of repository quality. The examples were selected because their public repository pages made README or structure patterns visible, not because they appeared in a ranking.

## Ranking observations

The order below is the displayed order observed on 10 November 2026, not a quality ranking by this note.

| Page checked | Interval shown | Leading displayed examples |
|---|---|---|
| [GitHub Trending daily](https://github.com/trending?since=daily) | Today | `anthropics/skills`, then `meta/astryx` |
| [GitHub Trending weekly](https://github.com/trending?since=weekly) | This week | `NVIDIA/auto-ontology`, then `vercel-labs/agent-desktop` |
| [GitHub Trending monthly](https://github.com/trending?since=monthly) | This month | `morluto/rea`, then `Nutlope/hallmark` |
| [Trendshift daily](https://trendshift.io/) | Today (UTC) | `meta/astryx`, then `sherlock-project/sherlock` |
| [Trendshift weekly](https://trendshift.io/weekly) | This week, 9 to 15 November | `meta/astryx`, then `sherlock-project/sherlock` |
| [Trendshift monthly](https://trendshift.io/monthly) | November 2026 | `storytold/craft-anything`, then `deepseek-ai/dsh-superagent-prototype` |
| [Trendshift yearly](https://trendshift.io/yearly) | 2026 | `openclaw/openclaw`, then `obra/superpowers`, then `morluto/rea` |

The Trendshift Daily view linked to the canonical homepage, which showed the Daily interval and "Today (UTC)". Its `/daily` route did not return extractable ranking content during the check, so the official homepage view is cited rather than substituting another ranking. All seven requested views were accessible through their stated or canonical pages.

## Repository examples and visible patterns

These are observations from the linked repository pages and README or file tree sections. Each reusable point is a design judgment, not a claim that the example is better or more suitable overall.

- [anthropics/skills](https://github.com/anthropics/skills), seen on [GitHub Trending daily](https://github.com/trending?since=daily), describes a self-contained folder per skill with a local `SKILL.md` and links to individual skill areas. **Judgment:** keep repeatable units self-contained and give each one a clear local entry document.
- [meta/astryx](https://github.com/meta/astryx), seen on [GitHub Trending daily](https://github.com/trending?since=daily) and [Trendshift weekly](https://trendshift.io/weekly), separates areas such as `apps/`, `docs/`, `internal/`, `packages/`, and `scripts/`. Its README states that the project is in beta. **Judgment:** make real ownership and implementation boundaries visible, and label maturity plainly. Do not copy its branding or technology choices.
- [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock), seen on [Trendshift daily](https://trendshift.io/) and [Trendshift weekly](https://trendshift.io/weekly), pairs a stated purpose with installation and command-line guidance; its visible tree includes source, tests, and docs areas. **Judgment:** a reader should find the purpose, setup path, and first useful command without searching through the repository.
- [Nutlope/hallmark](https://github.com/Nutlope/hallmark), seen on [GitHub Trending monthly](https://github.com/trending?since=monthly), visibly separates evaluation, screenshots and documentation, site, and skill areas. **Judgment:** keep evaluation artifacts and user-facing documentation discoverable, while adding only areas the project actually uses.
- [deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype), seen on [Trendshift monthly](https://trendshift.io/monthly), labels itself a research prototype and says it is not an official product. Its visible tree separates prompts, skills, source, tests, examples, setup, and docs. **Judgment:** state prototype status and limitations directly, and give distinct homes to prompts, tests, and documentation when those files exist.

## Design judgments for Smart Voicemail Router

### README

A useful landing page for this project should state its purpose and prototype status first, then show the intended workflow, the separation between complaint category, complaint urgency, customer state, voice evidence, and queue priority, and the local-first data boundary. It should link directly to the approved v1.2 documents, the CPU, GPU, and optional Colab guides, contribution rules, and evaluation guidance. It should say that labels and results are pending team review and measured evaluation. These are recommendations based on the project requirements and the observations above, not claims about ranking-page quality.

### Structure

Keep the approved project documents together under `docs/project/`, research notes under `docs/research/`, environment instructions and requirements in the planned `CPU case/`, `GPU case/`, and `Google Colab/` folders, and contribution rules at the root. When application work begins, add source, tests, and evaluation areas only with actual ownership and contract boundaries. This draft does not create application code or imply a finished runtime architecture.

Reuse the abstract documentation practices, not project names, logos, colors, copy, product claims, or technology stacks. Preserve the pair ownership and v1.2 decisions approved for Smart Voicemail Router.
