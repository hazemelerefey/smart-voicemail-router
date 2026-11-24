---
title: "From FusHa to Folk - Cross-Lingual Transfer in Arabic Language Models (VarDial 2026)"
tags: [svr, papers, arabic-nlp, cross-lingual-transfer, dialect-specific, "2026"]
source_url: "https://arxiv.org/abs/2602.09826"
---

# From FusHa to Folk: Exploring Cross-Lingual Transfer in Arabic Language Models

## What it is

A 2026 study (VarDial workshop, ACL 2026) that probes how Arabic language models transfer between Modern Standard Arabic and dialects, using probing on 3 NLP tasks and representational similarity. It compares MSA-centric models against dialect-specific models including EgyBERT, SaudiBERT, DarijaBERT, DziriBERT, and the AraRoBERTa family.

## Key findings

- Transfer between MSA and dialects is possible but disproportionate across dialects, partly explained by geographic proximity.
- There is evidence of negative interference in models trained to support all Arabic dialects at once.
- Dialect-specific models consistently exceed general-purpose encoders only when supported by substantial dialect pretraining data. Light dialect models (for example AraRoBERTa-EGY at 37.2M tokens) do not reliably beat general encoders.
- MSA-centric models demonstrate strong transferability to dialects and occasionally outperform dialect-specific models.

## Assessment for SVR

- This supports EgyBERT as first choice: at 1.07 billion tokens of Egyptian text it has the substantial pretraining data that the study says is required for a dialect-specific model to win.
- It works against AraRoBERTa-EGY: at 37.2M tokens it is below the scale where dialect-specific pretraining reliably pays off.
- It warns against assuming a dialect model always wins: the team must confirm EgyBERT on SVR validation data rather than trusting the dialect match alone.

## Sources

- Paper: https://arxiv.org/abs/2602.09826
- ACL Anthology: https://aclanthology.org/2026.vardial-1.16.pdf
