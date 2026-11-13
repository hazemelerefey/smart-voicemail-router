---
title: "wav2vec2 XLS-R - Multilingual Speech Encoder"
tags: [svr, models, speech, xls-r, wav2vec2, classification]
source_url: "https://huggingface.co/facebook/wav2vec2-xls-r-300m"
---

# wav2vec2 XLS-R

## What it is

XLS-R is a large scale multilingual pretrained speech model from Meta AI, Babu et al. 2022, based on wav2vec 2.0. It learns speech representations from unlabeled audio by masking parts of the audio and predicting them from context. It is the speech equivalent of XLM-R for text: one model for many languages.

## Hugging Face

- Model ID, 300M: `facebook/wav2vec2-xls-r-300m`
- Link: https://huggingface.co/facebook/wav2vec2-xls-r-300m
- Model ID, 1B: `facebook/wav2vec2-xls-r-1b`
- Link: https://huggingface.co/facebook/wav2vec2-xls-r-1b
- Model ID, 2B: `facebook/wav2vec2-xls-r-2b`
- Link: https://huggingface.co/facebook/wav2vec2-xls-r-2b

## Size

- 300M version: about 317M parameters.
- 1B version: about 917M parameters.
- 2B version: about 2,162M parameters.
- The 300M version is the practical choice for SVR. The 1B and 2B versions are much heavier and need more GPU memory and more data to fine tune safely.

## Training data

- Pretrained on 436,000 hours of unlabeled speech in 128 languages, from VoxPopuli, MLS, CommonVoice, BABEL, and VoxLingua107.
- Arabic is included, with about 95 hours of Arabic speech from Common Voice and VoxLingua107 in the pretraining mix. That is a small share of the total, so Arabic is present but not dominant.
- Input must be sampled at 16 kHz. This matches SVR exactly: SVR audio is 16 kHz mono WAV.

## Use for classification

- Yes, directly. XLS-R can be used in two ways.
- First, as a frozen feature extractor: freeze the encoder, take the hidden states, pool them over time, and train a small classification head. This is the SUPERB style setup and it works well on small datasets because few parameters are trained.
- Second, as a fine tuned encoder: add a classification head with `Wav2Vec2ForSequenceClassification` in Hugging Face Transformers, and fine tune the whole model or the top layers. This usually gives higher accuracy but needs more data and careful regularization on a small dataset.
- The model card states it should be fine tuned on a downstream task such as ASR, translation, or classification.

## Performance and literature

- On CoVoST-2 speech translation, XLS-R improved the previous state of the art by an average of 7.4 BLEU over 21 translation directions into English.
- For Arabic ASR, Whisper zero shot outperformed fully fine tuned XLS-R models on all datasets in the N-Shot Benchmarking of Whisper paper, Talafha et al. 2023, Interspeech. That is a warning: XLS-R needs fine tuning to compete, and its Arabic share is small.
- In multilingual speech emotion recognition, XLS-R variants were among the strongest models, with XLS-R 2B reported as the best in one 2026 evaluation, but the 2B size is not practical for SVR.
- In the KuralHub Arabic speech emotion benchmark on the ANAD dataset, frozen XLS-R 300M reached 61 percent test accuracy and XLS-R 1B reached 63 percent, behind Whisper large at 82 percent and WavLM large at 71 percent. That benchmark used a frozen backbone and a two layer head, so it measures representation quality, not full fine tuning.
- In Arabic pronunciation assessment work, a fine tuned XLS-R 1B system reached high recall, 79.20 percent, on the IqraEval 2025 task, and outperformed HuBERT and WavLM baselines in that study. Fine tuning matters more than the frozen comparison suggests.

## Assessment for SVR

- Strengths: multilingual, includes Arabic, 16 kHz native input, well supported in Hugging Face, 300M size is trainable, and it is the standard choice for low resource speech fine tuning.
- Weaknesses: Arabic is a small part of pretraining, and it has no Egyptian dialect specialization in the base model. Egyptian fine tuned versions exist and should be checked, see the mHuBERT and MMS note.
- Verdict: top recommendation for Angle 2, as the speech encoder to fine tune for direct audio classification. It is the best balance of Arabic coverage, size, and fine tuning support for a 12.6 hour dataset. Start with the 300M version, frozen first, then unfreeze the top layers.

## Source

- Model card: https://huggingface.co/facebook/wav2vec2-xls-r-300m
- Paper: Babu et al. 2022, XLS-R, arXiv 2111.09296.
