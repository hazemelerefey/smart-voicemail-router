---
title: "AceGPT - Localized Arabic Large Language Model"
tags: [svr, models, arabic-nlp, llm, acegpt]
source_url: "https://huggingface.co/FreedomIntelligence/AceGPT-7B"
---

# AceGPT

## What it is

AceGPT is a localized Arabic large language model from Freedom Intelligence, Huang et al. 2023. It starts from Llama 2 and adds Arabic localized pretraining, localized instruction tuning, and reinforcement learning from AI feedback. It was presented as the first open source Arabic LLM to complete the full pipeline of pretraining, supervised fine tuning, and reinforcement learning from feedback.

## Hugging Face

- Model ID, 7B: `FreedomIntelligence/AceGPT-7B`
- Link: https://huggingface.co/FreedomIntelligence/AceGPT-7B
- Chat 7B: `FreedomIntelligence/AceGPT-7B-chat`
- 13B: `FreedomIntelligence/AceGPT-13B`
- Chat 13B: `FreedomIntelligence/AceGPT-13B-chat`
- Link: https://huggingface.co/FreedomIntelligence/AceGPT-13B-chat

## Size

- 7B and 13B parameters, in base and chat versions.
- License: Apache 2.0. The base is Llama 2, so the Llama 2 license terms also apply to the underlying weights.

## Training data

- Localized pretraining: Llama 2 7B fine tuned on 30B tokens, Llama 2 13B fine tuned on 10B tokens, with Arabic and English data.
- Localized instruction tuning: supervised fine tuning with localized Arabic questions and responses, about 360,000 conversations, including native Arabic instructions and GPT-4 responses in Arabic.
- Localized RLAIF: reward model trained on localized preference data, about 11,000 preference samples, with PPO on about 30,000 samples.
- A new benchmark, ACVA, Arabic Cultural and Value Alignment, was released with the paper.

## Classification performance

- At release, AceGPT achieved state of the art among open source Arabic LLMs on Arabic Vicuna-80, Arabic AlpacaEval, Arabic MMLU, EXAMs, and ACVA.
- It outperformed ChatGPT on the Arabic Vicuna-80 benchmark when evaluated with GPT-4, despite the small scale of that benchmark.
- On ArabicMMLU zero shot, AceGPT-chat 13B averaged 50.3 percent accuracy, behind Jais-chat 30B at 60.6 percent and Jais-chat 13B at 52.4 percent in the same table.
- These are generation and knowledge benchmarks, not complaint classification. No published result shows AceGPT beating a fine tuned Arabic BERT encoder on a small imbalanced Arabic classification dataset.

## Egyptian dialect coverage

- No. AceGPT is localized for Arabic language and culture in general, with MSA as the main form. It is not Egyptian dialect specific.

## Assessment for SVR

- Strengths: strong Arabic instruction following, good cultural alignment for Arabic, and a complete open pipeline that the team can learn from.
- Weaknesses: decoder only, 7B minimum is far too large for the SVR classification job, no classification head, no Egyptian specialization, and the Llama 2 tokenizer has a small 32,000 token vocabulary that is mostly English, which gives poor Arabic token efficiency.
- Verdict: do not use as the main classifier. It is a useful reference for what localized Arabic LLMs can do, and a possible teacher or zero shot baseline, but it is the wrong shape for SVR training.

## Source

- Model: https://huggingface.co/FreedomIntelligence/AceGPT-7B
- Paper: Huang et al. 2023, AceGPT, Localizing Large Language Models in Arabic.
- Code: https://github.com/FreedomIntelligence/AceGPT
