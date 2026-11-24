---
title: "Categorization of Telecom Customers Complaints in Saudi Dialect Using Deep Learning Approach"
tags: [complaint-classification, telecom, saudi-dialect, aracust, svr-literature]
source_url: "https://doi.org/10.1109/NILES68063.2025.11232278"
---

# Categorization of Telecom Customers Complaints in Saudi Dialect Using Deep Learning Approach

- Authors: M. I. F. Moawad, A. A. M. Hassan, and M. M. Abdelwahab
- Year: 2025
- Venue: Proceedings of the 7th Novel Intelligent and Leading Emerging Sciences Conference (NILES), Giza, Egypt

## What they did

They built a deep learning model to categorize telecom customer complaints written in Saudi dialect into multiple complaint classes. Unlike satisfaction work, which is usually binary, this is a multi-class complaint categorization task, which is the closest published match to our complaint_category label.

## Model

Deep learning classifier trained on the AraCust data (the paper reports a dataset-based classification model for multi-class complaint categorization; the exact architecture is a deep neural classifier over Arabic text).

## Dataset

AraCust: Arabic tweets from Saudi telecom customers, used here for complaint categories rather than binary satisfaction.

## Results

- Accuracy of 87.64 percent on multi-class telecom complaint categorization

## Lesson for SVR

This paper sets a realistic reference point for our hardest label. Multi-class complaint categorization on dialectal telecom text reaches about 88 percent accuracy, noticeably below the 94 percent reported for binary satisfaction on the same AraCust data, which confirms that adding classes costs accuracy. For SVR, the implication is to expect complaint_category to be our lowest-scoring head and to judge it with macro F1 (which punishes weak rare classes) rather than accuracy. It also supports our data strategy: telecom complaint text is a good proxy domain, and the AraCust dataset is a candidate for auxiliary pretraining or for sanity-checking our classifier on external complaint text before trusting it on our own voicemails. One caution: the paper's reporting is thin on per-class metrics, so we should not copy its evaluation style; our audit page and per-class reports are the stronger approach.

## Source

https://doi.org/10.1109/NILES68063.2025.11232278
