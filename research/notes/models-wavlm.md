---
title: "WavLM - Large Scale Self Supervised Speech Model"
tags: [svr, models, speech, wavlm, classification]
source_url: "https://huggingface.co/microsoft/wavlm-large"
---

# WavLM

## What it is

WavLM is a large scale self supervised speech model from Microsoft, Chen et al. 2022. It is built on the HuBERT framework, with two additions: it models spoken content and preserves speaker identity, and it adds a denoising objective so it learns from noisy and overlapped speech. It was designed for full stack speech processing, not just ASR.

## Hugging Face

- Model ID, base plus: `microsoft/wavlm-base-plus`
- Link: https://huggingface.co/microsoft/wavlm-base-plus
- Model ID, large: `microsoft/wavlm-large`
- Link: https://huggingface.co/microsoft/wavlm-large
- Base: `microsoft/wavlm-base`

## Size

- Base and base plus: about 94.70M parameters.
- Large: about 316.62M parameters.
- Base is 12 layers, large is 24 layers.

## Training data

- Base: trained on LibriSpeech 960 hours.
- Base plus and large: trained on a mix of 94,000 hours from LibriLight, VoxPopuli, and GigaSpeech.
- English dominated. VoxPopuli adds some multilingual data, but WavLM is not an Arabic model and has no Egyptian dialect pretraining.

## Use for classification

- Yes, as a frozen feature extractor or as a fine tuned encoder. Hugging Face provides `WavLMForSequenceClassification`.
- WavLM performs especially well on speaker verification, speaker identification, and speaker diarization, which are speaker tasks, not content tasks.
- For emotion and state classification, which is relevant to the SVR customer_state label, WavLM is strong because it preserves speaker and prosody information.

## Performance and literature

- WavLM Large achieved state of the art performance on the SUPERB benchmark at release, with significant improvements on speaker and prosody tasks.
- In the KuralHub Arabic speech emotion benchmark on ANAD, frozen WavLM large reached 71 percent test accuracy, behind Whisper large at 82 percent, and ahead of HuBERT large at 66 percent, wav2vec2 large at 65 percent, and XLS-R 1B at 63 percent. WavLM base plus reached 61 percent.
- In a depression screening benchmark on English clinical interviews, partially fine tuning WavLM base, unfreezing only the last 2 of 12 layers, gave the strongest result at 0.641 F1, beating WavLM large at 0.613, HuBERT at 0.622, and wav2vec 2.0 at 0.604. The lesson is that partial fine tuning of a base model can beat full fine tuning of a large model on a small dataset, which is directly relevant to SVR with 12.6 hours of audio.

## Assessment for SVR

- Strengths: strong on speaker and emotion information, which helps customer_state, good frozen features, and the base plus model is small enough to fine tune partially on a small dataset.
- Weaknesses: no Arabic pretraining, so it is weaker than XLS-R and Whisper on Arabic content, and its strength is speaker identity, which SVR does not need to classify.
- Verdict: a useful second candidate for the customer_state label specifically, and a good model to test with partial fine tuning. Do not make it the main speech encoder for all four labels. The main encoder should be XLS-R 300M, which has multilingual and Arabic coverage.

## Source

- Model documentation: https://huggingface.co/docs/transformers/v4.15.0/model_doc/wavlm
- Model: https://huggingface.co/microsoft/wavlm-large
- Paper: Chen et al. 2022, WavLM, arXiv 2110.13900.
- Arabic emotion benchmark: https://aaivu.github.io/KuralHub/languages/arabic.html
