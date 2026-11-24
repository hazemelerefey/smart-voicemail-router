---
title: "Enhancing Arabic Sentiment Analysis via MARBERT: Domain Adaptation With Pseudo-Labeling and Contrastive Learning"
tags: [marbert, sentiment, pseudo-labeling, contrastive-learning, labr, svr-literature]
source_url: "https://onlinelibrary.wiley.com/doi/pdf/10.1002/eng2.70528"
---

# Enhancing Arabic Sentiment Analysis via MARBERT: Domain Adaptation With Pseudo-Labeling and Contrastive Learning

- Authors: Mohamed R. Ezzeldin, Gaber Sallam Salem Abdalla, and Abdoulie Faal
- Year: 2025
- Venue: Engineering Reports (Wiley)

## What they did

They improved MARBERT for Arabic sentiment analysis with domain adaptation: pseudo-labeling plus contrastive learning, on top of a careful preprocessing pipeline (normalization, removing links, hashtags and mentions, and reducing repeated letters).

## Model

MARBERT, fine-tuned with pseudo-labeling and contrastive learning for domain adaptation, using the MARBERT tokenizer.

## Dataset

LABR (Large-scale Arabic Book Reviews), a large and imbalanced Arabic sentiment dataset.

## Results

- Macro F1 score of 66.25 percent (plus or minus 0.49)
- Accuracy of 70.21 percent (plus or minus 0.43)

## Lesson for SVR

This paper is valuable precisely because its numbers are modest: LABR is hard, imbalanced, and realistic, much like our data, and it shows what macro F1 looks like when the classes are uneven. Three techniques transfer to us. First, pseudo-labeling: using the model to label additional unlabeled data and retraining on it, which we could apply to the 498 excluded voicemails or to any untranscribed audio once transcripts exist. Second, contrastive learning as a domain adaptation step, which helps the encoder separate classes that share vocabulary, such as our neighboring customer states. Third, the preprocessing recipe is concrete and reusable: normalize, strip links, hashtags and mentions, and collapse repeated letters, while keeping the dialect words intact. The gap between accuracy (70 percent) and macro F1 (66 percent) is also a reminder to report both numbers for every SVR head.

## Source

https://onlinelibrary.wiley.com/doi/pdf/10.1002/eng2.70528
