---
title: "EgyBERT: A Large Language Model Pretrained on Egyptian Dialect Corpora"
tags: [egyptian-dialect, pretraining, marbert, arabic-bert, svr-literature]
source_url: "https://arxiv.org/abs/2408.03524"
---

# EgyBERT: A Large Language Model Pretrained on Egyptian Dialect Corpora

- Author: Faisal Qarah
- Year: 2024
- Venue: arXiv preprint arXiv:2408.03524

## What they did

They pretrained a BERT-style model from scratch on Egyptian dialect text only, and compared it against five multidialect Arabic models on ten Egyptian dialect datasets covering sentiment analysis, text classification, sarcasm detection, and gender identification. They also released two new Egyptian corpora, the largest Egyptian dialect corpora reported in the literature at the time.

## Model

EgyBERT: 144M parameters, SentencePiece tokenizer with a 75K vocabulary, pretrained on 10.4 GB of Egyptian dialect text. Baselines: AraBERTv02-Twitter, QARiB, CAMeLBERT-DA, MARBERT, and MARBERTv2. The model is public on Hugging Face as faisalq/EgyBERT.

## Dataset

Egyptian Tweets Corpus (ETC): over 34.33 million tweets, 24.89 million sentences, 2.5 GB of text. Egyptian Forums Corpus (EFC): over 44.42 million sentences, 7.9 GB of text from Egyptian online forums. Evaluation used 10 public Egyptian dialect datasets.

## Results

- EgyBERT: average F1 of 84.25 percent and accuracy of 87.33 percent across the ten tasks, best overall
- MARBERTv2 second: F1 of 83.68 percent and accuracy of 87.19 percent
- The gap between EgyBERT and the multidialect models was consistent, showing that dialect-specific pretraining helps even against strong general dialect models

## Lesson for SVR

This is the single most relevant paper for our data, because our voicemails are Egyptian Arabic. The margin over MARBERTv2 is small (about 0.6 F1 points), but it is consistent across ten tasks, so EgyBERT deserves a place in our model shortlist next to MARBERTv2 and CAMeLBERT-DA. The practical trial to run is a head-to-head fine-tune of EgyBERT versus MARBERTv2 on our four tasks with identical hyperparameters, since the paper shows the winner can depend on the task. A second lesson is about data: the authors built their advantage from 10.4 GB of in-dialect text, which reminds us that our own 6,024 transcripts are small by pretraining standards, so fine-tuning a pretrained model is the right strategy and training from scratch is not. A third lesson is that Egyptian dialect models transfer across tasks (sentiment, sarcasm, gender), which supports our multi-task setup: one shared Egyptian-aware encoder can serve several heads.

## Source

https://arxiv.org/abs/2408.03524
