---
title: "Arabic Dialect Classification using RNNs, Transformers, and Large Language Models: A Comparative Analysis"
tags: [arabic-dialect, marbert, transformers, qadi, svr-literature]
source_url: "https://arxiv.org/abs/2506.19753v1"
---

# Arabic Dialect Classification using RNNs, Transformers, and Large Language Models: A Comparative Analysis

- Authors: Omar A. Essameldin, Ali O. Elbeih, Wael H. Gomaa, Wael F. Elsersy
- Year: 2025
- Venue: arXiv preprint arXiv:2506.19753 (also presented at IMSA 2025)

## What they did

They compared three families of models on the task of classifying 18 Arabic dialects: RNNs (LSTM and GRU on AraVec 3.0 embeddings with attention), fine-tuned transformers (AraBERT, CAMeLBERT-DA, E5, and MARBERT), and large language models through prompt engineering (zero-shot and few-shot). They also ran a dialect-level error analysis to see which dialects are easy and which are hard.

## Model

Best model: MARBERTv2 (fine-tuned). RNN baselines used LSTM and GRU with an attention layer. LLM prompting was tested as a zero-shot and few-shot classifier.

## Dataset

QADI: 440,000 Arabic tweets covering 18 country-level dialects. Four dialects (Somalia, Djibouti, Comoros, Mauritania) were excluded for lack of data.

## Results

- MARBERTv2: 65 percent accuracy and 64 percent F1 score, best overall
- LSTM performed slightly better than GRU on F1 among the RNNs, both clearly below the transformers
- LLMs were acceptable in zero-shot mode and got worse in few-shot mode, which the authors link to poor Arabic tokenization warping the example structure
- High-resource dialects scored well; low-resource dialects scored poorly

## Lesson for SVR

This is the most direct model-selection evidence for our setting. On dialectal Arabic text, a fine-tuned MARBERTv2 beats AraBERT, CAMeLBERT-DA, and general multilingual encoders, because it was pretrained on dialectal tweets. That supports starting our multi-task model from MARBERTv2 rather than AraBERT. The second lesson is about expectations: even the best model only reaches about 64 percent F1 on 18-way dialect classification, so fine-grained dialect labels are intrinsically hard and noisy. For SVR this argues for keeping the label set small and well separated (our 9 complaint categories, not 18 dialects), and for reporting per-class F1 so weak classes are visible instead of hidden behind accuracy. The third lesson is that few-shot LLM prompting underperforms fine-tuned encoders on Arabic dialect text, so LLM labeling should be treated as a noisy annotation aid, not as the classifier itself.

## Source

https://arxiv.org/abs/2506.19753v1
