---
title: "Sentiment Analysis on Arabic Dialects: A Multi-Dialect Benchmark"
tags: [arabic-dialect, sentiment, marbertv2, ahasis, shared-task, svr-literature]
source_url: "https://preview.aclanthology.org/manual-author-scripts/2025.ranlp-ahasis.13/"
---

# Sentiment Analysis on Arabic Dialects: A Multi-Dialect Benchmark

- Authors: Abdusalam F. Ahmad Nwesri, Nabila Almabrouk S. Shinbir, and Amani Bahlul Sharif
- Year: 2025
- Venue: Proceedings of the Shared Task on Sentiment Analysis for Arabic Dialects (AHaSIS) at RANLP 2025, pages 86-91, Varna, Bulgaria

## What they did

They took part in the AHaSIS shared task on sentiment analysis for Arabic dialects and fine-tuned six pretrained language models on hotel reviews written in Saudi and Moroccan (Darija) dialects, comparing them under one protocol. The shared task overall attracted over 40 registered teams, with 12 submitting systems.

## Model

Six fine-tuned models compared: AraBERT, AraBERTv02-Twitter (base and large), MARBERTv2, QARiB, and DarijaBERT. Best model: MARBERTv2.

## Dataset

860 hotel reviews in Saudi and Darija dialects, labeled positive, negative, or neutral, from the AHaSIS shared task data (derived from the Hotel Arabic Reviews Dataset, HARD).

## Results

- MARBERTv2: F1 score of 79 percent on the test set (0.779 in the detailed table), third place among 14 participants
- AraBERTv02-Twitter large reached 0.849 accuracy on validation but fell to 0.767 on test, showing a generalization gap
- The top system in the shared task overall reached an F1 of 0.81

## Lesson for SVR

This is a clean head-to-head benchmark of the exact models on our shortlist, run on dialectal text. MARBERTv2 wins again, and the runner-up pattern is instructive: a larger AraBERT variant looked best on validation and then dropped on test, which is a warning to trust only the held-out test split and to watch for overfitting when a model is tuned on validation. For our training protocol, the lesson is to keep the test set untouched (584 rows) and to select models on validation only. The paper also confirms that dialect-specific pretraining (MARBERTv2, DarijaBERT) beats general Arabic pretraining on dialect text, and that cross-dialect generalization is weak: a model trained on one dialect drops on another. Since all our data is Egyptian, this supports training on Egyptian data only rather than mixing dialects.

## Source

https://preview.aclanthology.org/manual-author-scripts/2025.ranlp-ahasis.13/
