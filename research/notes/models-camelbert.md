---
title: "CAMeLBERT - MSA, Dialectal, and Classical Arabic BERT Models"
tags: [svr, models, arabic-nlp, text-classification, camelbert, dialect]
source_url: "https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix"
---

# CAMeLBERT

## What it is

CAMeLBERT is a collection of BERT models from CAMeL Lab, Inoue et al. 2021, pretrained separately on Modern Standard Arabic (MSA), dialectal Arabic (DA), and classical Arabic (CA), plus a mix model trained on all three. The paper is "The Interplay of Variant, Size, and Task Type in Arabic Pre-trained Language Models."

## Hugging Face

- Mix model ID: `CAMeL-Lab/bert-base-arabic-camelbert-mix`
- Link: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix
- Dialect model ID: `CAMeL-Lab/bert-base-arabic-camelbert-da`
- Link: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-da
- MSA model ID: `CAMeL-Lab/bert-base-arabic-camelbert-msa`
- Link: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-msa

## Size

- BERT base architecture, about 110M parameters for the base models.
- Vocabulary: 30,000 WordPiece tokens.
- Mix model trained on 167 GB of text, 17.3B tokens. DA model on 54 GB, 5.8B tokens. MSA model on 107 GB, 12.6B tokens. CA model on 6 GB, 847M tokens.

## Training data

- MSA: Arabic Gigaword Fifth Edition, Abu El-Khair Corpus, OSIAN, Arabic Wikipedia, unshuffled Arabic OSCAR.
- DA: dialectal Arabic corpora, details on the model card.
- CA: OpenITI version 2020.1.2.
- Training: 1 million steps on a single cloud TPU v3-8, whole word masking, masked language model probability 0.15.

## Classification performance

- Evaluated on five tasks: named entity recognition, part of speech tagging, sentiment analysis, dialect identification, and poetry classification.
- The paper finding is that the best variant depends on the task type. The DA model helps on dialect tasks, the MSA model helps on MSA tasks, and the mix model is a good general choice.
- DialectSentEval 2026 Subtask 1, three class sentiment across four dialects: CAMeLBERT scored 81.96 percent macro F1, behind MARBERTv2 at 94.07 percent and ahead of AraBERTv2 at 79.77 percent.
- MuDRiC multi dialect commonsense validation: CAMeLBERT-mix averaged 72.34 percent accuracy, with 73.52 percent on Egyptian, behind MARBERTv2 at 78.16 percent average and 80.73 percent on Egyptian, and ahead of AraBERTv2 at 65.34 percent average.
- Cross dialect named entity recognition: CAMeLBERT-MSA was the best model for Egyptian in one MSA to dialect transfer setting, at 59.74 average F1, which shows the MSA variant can transfer to Egyptian, but MARBERTv2 was best for Egyptian in the dialect trained setting.

## Egyptian dialect coverage

- Yes, through the DA and mix models. The DA corpus includes Egyptian among other dialects, but it is not Egyptian only, and the DA model is smaller in training data than MARBERTv2.

## Assessment for SVR

- Strengths: the mix model covers MSA and dialect in one checkpoint, the DA variant is a focused dialect option, and the family is well studied so the team can test MSA vs DA vs mix on the same architecture.
- Weaknesses: in recent head to head dialect classification comparisons it sits behind MARBERTv2, and behind EgyBERT on Egyptian only tasks.
- Verdict: a useful second or third candidate, especially CAMeLBERT-mix and CAMeLBERT-DA. Include it in the model comparison if the team runs three encoders, but do not make it the default.

## Source

- Model card: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix
- Paper: Inoue et al. 2021, CAMeLBERT.
