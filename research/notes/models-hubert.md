---
title: "HuBERT - Self Supervised Speech Representation Learning"
tags: [svr, models, speech, hubert, classification]
source_url: "https://huggingface.co/facebook/hubert-large-ls960-ft"
---

# HuBERT

## What it is

HuBERT is a self supervised speech representation model from Meta AI, Hsu et al. 2021. It learns by predicting the cluster label of masked audio segments, using offline k-means clustering to create the targets. It combines acoustic and language modeling in one transformer, and it matches or outperforms wav2vec 2.0 on speech recognition, generation, and compression tasks.

## Hugging Face

- Model ID, base: `facebook/hubert-base-ls960`
- Link: https://huggingface.co/facebook/hubert-base-ls960
- Model ID, large: `facebook/hubert-large-ll60k`
- Link: https://huggingface.co/facebook/hubert-large-ll60k
- Fine tuned large: `facebook/hubert-large-ls960-ft`
- Link: https://huggingface.co/facebook/hubert-large-ls960-ft

## Size

- Base: about 94.68M parameters.
- Large: about 316.61M parameters.
- Base is 12 layers, large is 24 layers, both with 768 or 1024 hidden size depending on version.

## Training data

- Base: trained on LibriSpeech 960 hours of English read speech.
- Large: trained on LibriLight 60,000 hours of English speech.
- English only. There is no Arabic and no multilingual pretraining in the base HuBERT checkpoints. This is the central limitation for SVR.

## Use for classification

- Yes, as a frozen feature extractor or as a fine tuned encoder. Hugging Face provides `HubertForSequenceClassification`.
- The standard SUPERB protocol freezes the encoder, takes a weighted sum of layer outputs, and trains a small downstream head. That works well on small datasets.
- Partial fine tuning is also reported: in a depression screening benchmark, partially fine tuning HuBERT gave competitive results, but WavLM base with only the last 2 layers unfrozen beat it.

## Performance and literature

- HuBERT large reaches strong results on English ASR and on the SUPERB benchmark, and it is a standard baseline in speech representation work.
- For Arabic, the evidence is weaker. In the KuralHub Arabic speech emotion benchmark on ANAD, frozen HuBERT base reached 58 percent test accuracy and HuBERT large reached 66 percent, behind Whisper large at 82 percent and WavLM large at 71 percent.
- In Arabic speech emotion recognition on the BAVED dataset, 1,935 recordings from 61 speakers, wav2vec2 and HuBERT fine tunes were compared, and the wav2vec2 model reached 89 percent accuracy in that study, with HuBERT behind it.
- In Arabic pronunciation assessment, the IqraEval baseline uses mHuBERT, not English HuBERT, because the multilingual version is the relevant one for Arabic. See the mHuBERT note.

## Assessment for SVR

- Strengths: small base model, well supported, strong English representations, and a clean classification interface in Hugging Face.
- Weaknesses: English only pretraining is a poor match for Egyptian Arabic speech. Every Arabic comparison in this research places it behind multilingual models and behind Whisper.
- Verdict: do not use as the main speech encoder for SVR. Use it only as a control baseline if the team wants to show that Arabic aware pretraining matters. Prefer XLS-R or Whisper encoder features.

## Source

- Model card: https://huggingface.co/facebook/hubert-large-ls960-ft
- Paper: Hsu et al. 2021, HuBERT, arXiv 2106.07447.
- Arabic emotion benchmark: https://aaivu.github.io/KuralHub/languages/arabic.html
