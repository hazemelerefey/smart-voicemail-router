---
title: "Arabic Specific Speech Models - mHuBERT, MMS, and Egyptian XLSR"
tags: [svr, models, speech, arabic, mhubert, mms, egyptian-dialect]
source_url: "https://huggingface.co/facebook/mhubert-base-147"
---

# Arabic Specific Speech Models: mHuBERT, MMS, and Egyptian XLSR

## What this note covers

The base speech models above are multilingual or English only. This note covers the models that are closer to Arabic: mHuBERT, Meta MMS, and Egyptian fine tuned XLS-R checkpoints. These are the most relevant speech models for SVR after XLS-R itself.

## mHuBERT

### What it is

mHuBERT is a multilingual version of HuBERT, trained on 147 languages. It is the baseline model for the IqraEval Arabic pronunciation assessment shared task, which is the closest public Arabic speech task to SVR in style.

### Hugging Face

- Model ID: `facebook/mhubert-base-147`
- Link: https://huggingface.co/facebook/mhubert-base-147

### Size

- About 94M parameters, base size.

### Training data and performance

- Pretrained on 147 languages, including Arabic.
- IqraEval baseline: frozen mHuBERT encoder, SUPERB style weighted layer sum, plus a 2 layer 1024 unit Bi-LSTM with CTC loss, trained with Adam at learning rate 1e-4 and batch size 16. It reached an F1 score of 0.4414 on the QuranMB.v2 evaluation set. That is a lower bound reference, not a strong result, and it shows that a frozen multilingual encoder alone is not enough for Arabic phoneme tasks without fine tuning.

### Assessment for SVR

- A reasonable frozen feature extractor for Arabic, smaller than XLS-R 1B and Whisper large, but there is no published Arabic classification result that puts it ahead of XLS-R 300M. Use it as a third candidate if the team tests frozen features.

## MMS, Massively Multilingual Speech

### What it is

MMS is Meta's massively multilingual speech model, Pratap et al. 2024, based on wav2vec 2.0, covering over 1,000 languages. It is the largest language coverage of any speech model in this set.

### Hugging Face

- Model ID, 1B: `facebook/mms-1b-all`
- Link: https://huggingface.co/facebook/mms-1b-all
- Smaller versions exist, including `facebook/mms-300m`.

### Size

- 1B version: about 1,000M parameters.
- 300M version: about 300M parameters.

### Training data and performance

- Pretrained on over 1,000 languages, including Arabic.
- On the SADA Arabic ASR dataset, MMS 1B fine tuned with a 4 gram language model reached 40.9 percent WER on the SADA test clean set, which shows how hard dialectal Arabic ASR is, even for a 1B multilingual model.

### Assessment for SVR

- Too large and too general for SVR as a first choice. The 300M version could be tested as a frozen extractor, but XLS-R 300M has a stronger published record for fine tuning on small datasets.

## Egyptian fine tuned XLS-R

### What it is

Community fine tunes of XLS-R on Egyptian Arabic ASR. The best documented one in this research is by Ibrahim Amin, based on an Egyptian fine tune by Omar Adel.

### Hugging Face

- Model ID: `IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53`
- Link: https://huggingface.co/IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53
- Base: `omarxadel/wav2vec2-large-xlsr-53-arabic-egyptian`

### Training data

- Trained on YouTube Egyptian Arabic speech, MASC, Common Voice 15 Arabic, MGB-3 broadcast speech, and the Arabic Speech Corpus.
- Focused on real life Egyptian Arabic, spontaneous and conversational, which is close to SVR voicemail style.

### Performance

- The author reports 27.20 percent WER on a Common Voice 17.0 Arabic test subset, against 47.22 percent for an Arabic XLS-R 300M fine tune and 52.36 percent for Whisper large-v3 in the same table. Treat this as author reported, not as an independent benchmark, because the decoding and normalization settings differ across rows.
- The direction is still useful: an Egyptian fine tuned XLS-R can beat a general Whisper on Egyptian ASR in that author's setup.

### Assessment for SVR

- This is the speech equivalent of EgyBERT: the only Egyptian specific speech checkpoint found in this research. It is a CTC ASR model, not a classifier, so the team cannot use it directly for classification. They can use it in two ways: as a starting point for fine tuning a classification head, by replacing the CTC head, or as a better transcription model to test against Whisper large-v3 for SVR transcripts.
- Check the license, the training data, and the checkpoint quality before using it in the project. Community ASR checkpoints vary in quality.

## Emerging Arabic speech model: Ara-BEST-RQ

- A 2026 Arabic focused BEST-RQ conformer model, 300M and 600M versions, pretrained on 5,640 hours of crawled speech plus public data.
- Reported in the Arabic Speech Handbook, compiled August 2026, to beat HuBERT and XLS-R class baselines on MGB-3, MGB-5, TARIC-SLU, and Common Voice 19. This is a handbook summary, not a peer reviewed paper, so treat it as a lead to verify, not as a proven result.
- If a public checkpoint exists, it is worth checking, because focused Arabic pretraining beats massive multilingual pretraining at equal size in that report.

## Source

- mHuBERT: https://huggingface.co/facebook/mhubert-base-147
- MMS: https://huggingface.co/facebook/mms-1b-all
- Egyptian XLSR: https://huggingface.co/IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53
- IqraEval baseline: https://arxiv.org/html/2603.29087
- Arabic Speech Handbook: https://github.com/h9-tec/Arabic-Speech-Handbook/blob/HEAD/README.md
