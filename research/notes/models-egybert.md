---
title: "EgyBERT - Egyptian Dialect Only BERT"
tags: [svr, models, arabic-nlp, text-classification, egybert, egyptian-dialect]
source_url: "https://huggingface.co/faisalq/EgyBERT"
---

# EgyBERT

## What it is

EgyBERT is a BERT model pretrained only on Egyptian dialect text, by Faisal Qarah, Taibah University, 2024. It is the only model in this set that is Egyptian only by design, which makes it the most directly relevant encoder for SVR, whose voicemails are Egyptian Arabic.

## Hugging Face

- Model ID: `faisalq/EgyBERT`
- Link: https://huggingface.co/faisalq/EgyBERT

## Size

- BERT base architecture: 12 encoder layers, 12 attention heads per layer, 768 hidden size.
- Vocabulary: 75,000 WordPiece tokens.
- The paper does not state a single parameter total in the abstract; treat it as BERT base class, about 110M to 135M parameters depending on vocabulary and embedding size, and confirm the exact count from the checkpoint config before reporting it.

## Training data

- Total: 10.4 GB of Egyptian dialectal text.
- Egyptian Tweets Corpus (ETC): over 34.33 million tweets, 24.89 million sentences, 2.5 GB of text.
- Egyptian Forums Corpus (EFC): over 44.42 million sentences, 7.9 GB of text, collected from Egyptian online forums.
- No MSA news corpus and no other dialect corpus. This is a deliberate trade: depth in one dialect instead of breadth across dialects.

## Classification performance

- Evaluated against five multi dialect Arabic models on 10 publicly available Egyptian dialect datasets covering sentiment analysis, text classification, sarcasm detection, and gender identification.
- EgyBERT achieved the highest average F1 score of 84.25 percent and average accuracy of 87.33 percent.
- MARBERTv2 was second, at 83.68 percent F1 and 87.19 percent accuracy. The margin over MARBERTv2 is small, 0.57 points of F1, but it is consistent with the design: Egyptian only pretraining beats multi dialect pretraining on Egyptian tasks.
- The other models in the comparison were AraBERTv02-Twitter, QARiB, CAMeLBERT-DA, MARBERTv1, and MARBERTv2.

## Egyptian dialect coverage

- Yes, exclusively. This is its whole point. The training data, the evaluation, and the vocabulary are Egyptian.

## Assessment for SVR

- Strengths: exact dialect match to SVR data, best published average on Egyptian classification tasks, BERT base size so it fits the same training setup as MARBERTv2, and the small margin over MARBERTv2 is still a win on the target dialect.
- Weaknesses: single author model from 2024, less widely used and less battle tested than MARBERTv2, so the team should check the checkpoint loads cleanly, check the tokenizer on SVR transcripts, and verify that it handles MSA words that appear in complaints. The paper evaluation is on tweets and short texts, not on transcribed voicemail, so the advantage must be confirmed on SVR validation data.
- Verdict: top recommendation for Angle 1, jointly with MARBERTv2 as the fallback. Run both with the same multi task heads, same splits, and same class weighting, and pick by macro F1 on the validation set, with extra attention to the rare churn at risk class.

## Source

- Paper: Qarah, EgyBERT, arXiv 2408.03524, August 2024. Link: https://arxiv.org/abs/2408.03524
- Model: https://huggingface.co/faisalq/EgyBERT
