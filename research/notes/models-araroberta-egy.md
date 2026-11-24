---
title: "AraRoBERTa-EGY - Egyptian Dialect RoBERTa"
tags: [svr, models, arabic-nlp, text-classification, araroberta, egyptian-dialect]
source_url: "https://huggingface.co/reemalyami/AraRoBERTa-EGY"
---

# AraRoBERTa-EGY

## What it is

AraRoBERTa-EGY is a RoBERTa-base encoder pretrained only on Egyptian dialect, by Reem AlYami and Rabah Al-Zaidy, 2022. It is one of seven mono-dialectal AraRoBERTa models, each trained on a single country-level dialect. It is peer reviewed (WANLP 2022, "Weakly and Semi-Supervised Learning for Arabic Text Classification using Monodialectal Language Models").

## Hugging Face

- Model ID: `reemalyami/AraRoBERTa-EGY`
- Link: https://huggingface.co/reemalyami/AraRoBERTa-EGY

## Size and training data

- RoBERTa base architecture.
- Pretrained on 37.2 million tokens of Egyptian dialect text. This is much smaller than EgyBERT at 1.07 billion tokens and MARBERTv2 at about 1 billion tweets.

## Assessment for SVR

- Strengths: Egyptian only by design, peer reviewed, RoBERTa architecture is a proven classifier, and it is the only other Egyptian-specific encoder besides EgyBERT.
- Weaknesses: the pretraining corpus is small (37.2M tokens), so its representations are thinner than EgyBERT and MARBERTv2. The 2026 VarDial cross-lingual transfer study found that dialect-specific models beat general models only when supported by substantial pretraining data, which works against AraRoBERTa-EGY at this size.
- Verdict: mention it as a candidate for completeness, but do not recommend it as a first or second choice. EgyBERT and MARBERTv2 both have far more pretraining data. Use it only as an extra comparison if the team has spare time.

## Sources

- Model: https://huggingface.co/reemalyami/AraRoBERTa-EGY
- Paper: AlYami and Al-Zaidy, 2022, WANLP. Link: https://aclanthology.org/2022.wanlp-1.18/
