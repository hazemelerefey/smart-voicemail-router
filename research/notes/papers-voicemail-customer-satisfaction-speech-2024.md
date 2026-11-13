---
title: "Cross-transfer Knowledge between Speech and Text Encoders to Evaluate Customer Satisfaction"
tags: [voicemail, call-center, customer-satisfaction, whisper, wav2vec2, speech, svr-literature]
source_url: "https://publications.idiap.ch/downloads/papers/2024/Parra-Gallego_INTERSPEECH_2024.pdf"
---

# Cross-transfer Knowledge between Speech and Text Encoders to Evaluate Customer Satisfaction

- Authors: Luis Felipe Parra-Gallego, Tilak Purohit, Bogdan Vlasenko, Juan Rafael Orozco-Arroyave
- Year: 2024
- Venue: INTERSPEECH 2024

## What they did

They tackled customer satisfaction evaluation on call center voicemails, comparing the standard pipeline (ASR transcript, then a text classifier) against end-to-end spoken language understanding that classifies directly from audio. Their key method is cross-transfer knowledge distillation: linguistic knowledge from a BERT text model is distilled into speech encoders, so the speech model learns text-like representations and no longer needs an ASR transcript at inference time.

## Model

Speech encoders tested: Wav2Vec2, WavLM, and the Whisper encoder, each enriched with BERT knowledge through cross-transfer distillation. Text baseline: BERT representations of the ASR transcript.

## Dataset

A call center dataset of customer voicemails (Konecta Group), labeled satisfied versus unsatisfied. Customer satisfaction in call centers is normally judged by quality experts on a small sample of recordings.

## Results

- Over 92 percent accuracy in identifying customer satisfaction categories from voicemail audio
- The distilled speech encoders beat the plain ASR-then-text pipeline, because ASR errors propagate into the text classifier
- The approach is faster and cheaper at inference because it removes the ASR step

## Lesson for SVR

This is the closest paper to our full pipeline: voicemail audio in, customer satisfaction out. Three lessons. First, it validates the product idea end to end: classifying satisfaction from voicemails works at over 92 percent in a real call center setting. Second, it warns us about our own pipeline risk: our labels are trained on Whisper transcripts, so transcription errors become label noise, and a future version of SVR could add acoustic features or a distilled speech encoder to recover signal the transcript loses (tone, pauses, emphasis), which is especially relevant for our customer_state label. Third, the distillation idea is a practical middle path: we do not need to replace our text model, but we can experiment with adding a small audio feature branch later, once the text model is stable. For now, the paper supports keeping Whisper large-v3 as the transcription step and documenting transcript quality as a known error source.

## Source

https://publications.idiap.ch/downloads/papers/2024/Parra-Gallego_INTERSPEECH_2024.pdf
