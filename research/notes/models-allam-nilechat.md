---
title: "ALLaM and Nile-Chat - Newer Arabic LLMs"
tags: [svr, models, arabic-nlp, llm, allam, nile-chat, newer]
source_url: "https://huggingface.co/ALLaM-AI"
---

# ALLaM and Nile-Chat

## What this note covers

Two newer Arabic LLM families that were not in the original task list but matter for completeness: ALLaM, the Saudi Arabic LLM family, and Nile-Chat, the Egyptian focused LLM from 2025. Both are decoder only LLMs, so neither is a direct classifier for SVR, but both show where Arabic LLMs are heading.

## ALLaM

### What it is

ALLaM is the Arabic Large Language Model family from SDAIA, the Saudi Data and AI Authority, later HUMAIN. It was published as a conference paper at ICLR 2025. It is a bilingual Arabic and English LLM, trained for language alignment and knowledge transfer at scale.

### Hugging Face

- Organization: `ALLaM-AI`
- Link: https://huggingface.co/ALLaM-AI
- The 7B instruct model is openly available on Hugging Face under Apache 2.0. The 13B model ships through Microsoft Azure AI Foundry and IBM watsonx under a SDAIA license rather than as open weights. The 34B model is closed.

### Size

- Models at 7B, 13B, 34B, and 70B scales, initialized from Llama 2 weights, plus 7B and 34B models trained from scratch.
- The 13B model is reported as pretrained on over 3 trillion tokens in Arabic and English in secondary reporting; confirm this number from the paper before citing it in a formal document.

### Training data and performance

- Training covers Arabic and English transfer, alignment, and human preference optimization, with 25,854 human preference samples in Arabic and English reported in the paper.
- ALLaM achieves state of the art performance on Arabic benchmarks including Arabic MMLU, ACVA, and Arabic Exams, and improves English performance over the original Llama 2 base.
- On Arabic MMLU, ALLaM instruct models lead the Arabic LLM comparison in the paper figure, ahead of Jais and AceGPT.

### Assessment for SVR

- Do not use as the main classifier. It is a large decoder LLM with no Egyptian specialization and no classification head. It is useful as a reference for Arabic LLM quality and as a possible teacher model.

## Nile-Chat

### What it is

Nile-Chat is a 2025 Egyptian language model family for Arabic and Latin scripts, by Shang et al., presented at the ArabicNLP Workshop 2025. It is the first LLM family in this research that is explicitly Egyptian focused, which makes it relevant to SVR even though it is a generative model, not an encoder.

### Source

- Paper: Shang et al. 2025, Nile-Chat, Egyptian Language Models for Arabic and Latin Scripts. Link: https://aclanthology.org/2025.arabicnlp-main.25.pdf
- No Hugging Face model ID was verified in this research, so no HF link is given here. The team should check the paper repository before using it.

### Assessment for SVR

- Interesting as a future Egyptian teacher model or for Egyptian generation, but not a classifier. Do not plan SVR training around it until a public checkpoint and a classification result are confirmed.

## Source

- ALLaM organization: https://huggingface.co/ALLaM-AI
- ALLaM paper: ICLR 2025, https://openreview.net/notes/edits/attachment?id=EnFQdWJFiQ&name=pdf
- Nile-Chat paper: https://aclanthology.org/2025.arabicnlp-main.25.pdf
