---
title: "Yet Another Model for Arabic Dialect Identification"
tags: [arabic-dialect, speech, ecapa-tdnn, unispeech, egyptian, svr-literature]
source_url: "https://pub-fad10fba280c45dba0823fd585acc08c.r2.dev/pdf/doi-10.18653-v1-2023.arabicnlp-1.37.pdf?v=1789105761"
---

# Yet Another Model for Arabic Dialect Identification

- Authors: Ajinkya Kulkarni and Hanan Aldarmaki
- Year: 2023
- Venue: Proceedings of ArabicNLP 2023, pages 435-440

## What they did

They built a spoken Arabic dialect identification model that works directly on audio instead of text. They tested two architectures (ResNet and ECAPA-TDNN) with two kinds of acoustic features (MFCCs and features from the pretrained self-supervised model UniSpeech-SAT Large), plus a fusion of all four variants. The goal was to route dialectal utterances to dialect-specific speech recognition modules.

## Model

Best model: fusion of ECAPA-TDNN and ResNet classifiers using both MFCC features and UniSpeech-SAT Large embeddings. Individually, ECAPA-TDNN beat ResNet, and UniSpeech-SAT features beat MFCCs by a large margin.

## Dataset

ADI-5 (from the MGB-3 challenge): 5 varieties including Egyptian, Levantine, Gulf, North African, and Modern Standard Arabic. ADI-17 (from MGB-5): 17 Arabic dialects. Both are broadcast speech datasets.

## Results

- ADI-5: 84.7 percent accuracy, up from 75 percent previously reported
- ADI-17: 96.9 percent accuracy, up from 93.1 percent (UKent system)
- Fusion of all four variants consistently beat every individual model

## Lesson for SVR

This paper matters for the audio side of our pipeline, which is usually treated as solved once Whisper produces a transcript. Two lessons. First, self-supervised speech embeddings (UniSpeech-SAT here, and by extension wav2vec2, HuBERT, or Whisper encoder features) carry far more dialect and speaker information than handcrafted MFCC features, so if we ever add an audio branch to the model, pretrained speech embeddings are the right input. Second, Egyptian is one of the five ADI-5 varieties and the model separates it well in speech, which is encouraging for the idea that acoustic cues could help disambiguate transcripts where the text alone is ambiguous. For now the practical use is narrow: keep this paper as the reference if the team later experiments with audio features alongside text, and note that fusion (combining several models or feature types) reliably beats single models in this literature.

## Source

https://pub-fad10fba280c45dba0823fd585acc08c.r2.dev/pdf/doi-10.18653-v1-2023.arabicnlp-1.37.pdf?v=1789105761
