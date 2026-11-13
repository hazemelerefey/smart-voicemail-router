---
title: "Whisper - Multilingual Speech Recognition and Encoder"
tags: [svr, models, speech, whisper, asr, classification]
source_url: "https://huggingface.co/openai/whisper-large-v3"
---

# Whisper

## What it is

Whisper is an encoder decoder speech model from OpenAI, Radford et al. 2022, trained on weakly supervised multilingual audio with transcripts. It is primarily an automatic speech recognition model, and it also does language identification, voice activity detection, and speech translation. SVR already uses Whisper large-v3 for transcription, so this note covers whether the same model can also be used for classification.

## Hugging Face

- Model ID, large v3: `openai/whisper-large-v3`
- Link: https://huggingface.co/openai/whisper-large-v3
- Turbo: `openai/whisper-large-v3-turbo`
- Link: https://huggingface.co/openai/whisper-large-v3-turbo
- Smaller sizes: `openai/whisper-tiny`, `openai/whisper-base`, `openai/whisper-small`, `openai/whisper-medium`

## Size

- Tiny: 39M parameters.
- Base: 74M parameters.
- Small: 244M parameters.
- Medium: 769M parameters.
- Large, large v2, large v3: 1,550M parameters.
- Large v3 Turbo: 809M parameters. It keeps the large v3 encoder and cuts the decoder from 32 layers to 4, which makes it 4 to 8 times faster with only a small accuracy drop. Turbo does not support translation.

## Training data

- Trained on 680,000 hours of multilingual and multitask supervised audio from the web. Large v3 adds 1M hours weakly labeled plus 4M hours pseudo labeled, for a total of 5M hours in the v3 training description.
- Arabic: about 739 hours of labeled Arabic speech in the original training set.
- Languages: 99 languages. Input is a log Mel spectrogram, 128 Mel bins in v3, up from 80 in v2. Audio is processed in fixed 30 second windows, with shorter audio padded.

## Use for classification

- Whisper is not a classifier out of the box. There is no classification head in the released model.
- It can be used for classification in three ways.
- First, as a frozen feature extractor: take the encoder hidden states, pool them over time, and train a small classification head. This is the setup used in the KuralHub benchmark below.
- Second, by fine tuning the encoder with a classification head, freezing or discarding the decoder. This needs custom code, because Hugging Face does not ship a WhisperForSequenceClassification class in the same way as for wav2vec2.
- Third, indirectly: SVR already does this. Whisper transcribes the audio, and the text classifier labels the transcript. That is the current SVR pipeline, and it is the simplest and most explainable route.

## Performance and literature

- Whisper zero shot outperformed fully fine tuned XLS-R models on all Arabic ASR datasets in Talafha et al. 2023, Interspeech, N-Shot Benchmarking of Whisper on Diverse Arabic Speech Recognition. Its performance dropped sharply on five unseen dialects: Algeria, Jordan, Palestine, UAE, and Yemen.
- On the Open Universal Arabic ASR Leaderboard, Whisper large v3 is a strong general Arabic ASR model, but dialectal Arabic remains hard. Word error rates on dialectal test sets are around 50 percent in that leaderboard, which is why SVR transcripts are noisy and why the text classifier must be robust to transcription errors.
- In the KuralHub speech emotion benchmark, 29 languages, frozen backbone plus a two layer head, Whisper large was the best Arabic model: 82.0 percent test accuracy on the ANAD Arabic dataset, with macro F1 0.81, against 71 percent for WavLM large, 66 percent for HuBERT large, 65 percent for wav2vec2 large, and 61 to 63 percent for XLS-R 300M and 1B. The mean across all 11 models was 66.1 percent. This is strong evidence that Whisper encoder features carry emotion and speaker state information, which is relevant to the SVR customer_state label.
- Whisper large v3 is already the SVR transcription model, and the project found Whisper large-v3 beats turbo on word error rate, 0.29 against 0.35, on SVR data.

## Assessment for SVR

- Strengths: best Arabic ASR in the comparison, strongest frozen features for Arabic emotion in the KuralHub benchmark, already in the SVR pipeline, and the encoder is well trained on Arabic speech.
- Weaknesses: 1.55B parameters is too large to fine tune fully on 12.6 hours of audio, no native classification head, and the 30 second window and Mel spectrogram input are heavier than the raw waveform input of wav2vec2.
- Verdict: keep Whisper large-v3 for transcription, which is its proven role in SVR. For direct audio classification, test its frozen encoder features as a second candidate, but make XLS-R 300M the first speech encoder to fine tune, because it is smaller, has a native classification class, and is easier to train on a small dataset.

## Source

- Model card: https://huggingface.co/openai/whisper-large-v3
- Paper: Radford et al. 2022, Robust Speech Recognition via Large-Scale Weak Supervision.
- Arabic benchmark: Talafha et al. 2023, https://ar5iv.labs.arxiv.org/html/2306.02902
- Emotion benchmark: https://aaivu.github.io/KuralHub/languages/arabic.html
