---
title: "Jais - Arabic Centric Large Language Model"
tags: [svr, models, arabic-nlp, llm, jais]
source_url: "https://huggingface.co/core42/jais-13b"
---

# Jais

## What it is

Jais is a family of Arabic centric bilingual Arabic and English large language models, developed by Inception (G42), MBZUAI, and Cerebras Systems, Sengupta et al. 2023. It is a decoder only transformer, trained from scratch, for generation and instruction following. It is not an encoder for classification.

## Hugging Face

- Model ID, 13B: `core42/jais-13b`
- Link: https://huggingface.co/core42/jais-13b
- Chat 13B: `core42/jais-13b-chat`
- Small family: `inceptionai/jais-family-590m`, `inceptionai/jais-family-1p3b`, and larger sizes up to 30B and 70B.
- Link for the small family: https://huggingface.co/inceptionai/jais-family-590m

## Size

- Original release: 13B and 30B parameters.
- Later family, August 2024: 20 foundation and chat models across eight sizes, 590M, 1.3B, 2.7B, 6.7B, 7B, 13B, 30B, and 70B.
- Jais 2, announced December 2025: 8B and 70B chat checkpoints.
- License: Apache 2.0. Some repositories require accepting access conditions before download.

## Training data

- Original paper: trained from scratch on 72B Arabic tokens, plus English and code, then fine tuned on 3.6M instruction tuning samples.
- The 13B release is reported with 395B total tokens in later summaries: 116B Arabic and 279B English.
- Jais 30B v3 is reported with about 1.639T tokens: 971B English, 475B Arabic, and 193B code.
- The training data is mainly MSA and general Arabic, not Egyptian dialect specific.

## Classification performance

- Jais was state of the art among open Arabic models on Arabic benchmarks at release, including ArabicMMLU style tasks.
- On ArabicMMLU zero shot, Jais-chat 30B averaged 60.6 percent accuracy, and Jais-chat 13B averaged 52.4 percent, ahead of AceGPT-chat 13B at 50.3 percent in that table, but these are knowledge and reasoning benchmarks, not text classification of complaints.
- For classification, a decoder LLM is used by prompting or by fine tuning with LoRA to output a label. That works, but it is far heavier than a BERT encoder, harder to calibrate for four simultaneous labels, and harder to explain, which matters for SVR because tickets must be explainable.

## Egyptian dialect coverage

- Partial. Jais covers Arabic dialects in general, but it is not Egyptian specific. In the AraDiCE dialect benchmark, Jais 13B performed solidly on Egyptian Arabic but behind Fanar 8.7B in Egyptian contexts.

## Assessment for SVR

- Strengths: strong general Arabic understanding, useful as a teacher model or as a zero shot baseline, and the small 590M and 1.3B family members are cheap enough to test.
- Weaknesses: decoder only, 13B and 30B are too large for a small imbalanced classification dataset, no classification head, no Egyptian specialization, and gated access adds friction.
- Verdict: do not use as the main classifier. Consider it only as a baseline for prompting, or as a teacher for distillation if the team later wants that, and prefer the small family members if they test it at all.

## Source

- Model: https://huggingface.co/core42/jais-13b
- Paper: Sengupta et al. 2023, Jais.
