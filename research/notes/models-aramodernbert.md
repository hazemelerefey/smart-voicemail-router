---
title: "AraModernBERT - ModernBERT Encoder for Arabic"
tags: [svr, models, arabic-nlp, text-classification, aramodernbert, newer]
source_url: "https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0"
---

# AraModernBERT

## What it is

AraModernBERT is a newer Arabic encoder built on the ModernBERT architecture, by the NAMAA Community, Elshehy et al. 2025 and 2026. ModernBERT is a modernized encoder with alternating attention, longer context, and better efficiency than BERT. AraModernBERT adapts it to Arabic with a new Arabic tokenizer and transtokenized embedding initialization, which initializes the new Arabic embeddings from semantically aligned embeddings of a source model instead of random initialization.

## Hugging Face

- Model ID: `NAMAA-Space/AraModernBert-Base-V1.0`
- Link: https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0
- Note the spelling in the ID: AraModernBert, with a lower case b in Bert.

## Size

- About 149M parameters.
- Architecture: 22 transformer layers, 768 hidden size, 12 attention heads, intermediate size 1152.
- Vocabulary: 50,280 tokens, specialized for Arabic.
- Context length: 8,192 tokens, far longer than the 512 token limit of BERT models. This matters for long voicemail transcripts.

## Training data

- Trained on 100 GB of Arabic text with masked language modeling.
- The paper reports stable Arabic encoder training through transtokenization and effective native long context modeling up to 8,192 tokens.
- The model card states it is optimized for Modern Standard Arabic and may show varying performance on dialectal Arabic variants or classical Arabic texts.

## Classification performance

- The paper reports a comprehensive evaluation on intrinsic language modeling, downstream Arabic natural language understanding tasks, retrieval, and named entity recognition, with strong downstream transfer and stable long context modeling.
- No published head to head result was found in this research that places AraModernBERT against MARBERTv2 or EgyBERT on Egyptian dialect classification specifically. That comparison is still missing, so the team should not assume it beats the dialect models.
- It is already used as a base for fine tuning in shared tasks, for example as a retriever fine tuned for Quran and Hadith question answering, which shows the checkpoint is usable in practice.

## Egyptian dialect coverage

- Limited by design. The card warns about varying performance on dialectal variants. The training data is Arabic in general, with MSA as the focus, not Egyptian only.

## Assessment for SVR

- Strengths: modern architecture, 8,192 token context removes the truncation problem for long voicemails, similar size to BERT base so training cost is similar, and a larger Arabic vocabulary than CAMeLBERT.
- Weaknesses: MSA focus is a mismatch for Egyptian dialect, and there is no published Egyptian classification result to support it over MARBERTv2 or EgyBERT.
- Verdict: a promising third candidate, worth testing if the team has time for a three way comparison. Test it on the same splits and report macro F1. If long transcripts are truncated by BERT models in practice, AraModernBERT becomes more attractive, but dialect accuracy comes first.

## Source

- Model card: https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0
- Paper: Elshehy et al. 2026, AraModernBERT, Transtokenized Initialization and Long-Context Encoder Modeling for Arabic.
