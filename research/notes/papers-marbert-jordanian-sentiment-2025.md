---
title: "Fine-Tuning MARBERT for Sentiment Analysis in Jordanian Arabic Dialects Using a Synthetic Dialectal Corpus"
tags: [marbert, sentiment, jordanian-dialect, fine-tuning, svr-literature]
source_url: "https://alkindipublishers.org/index.php/jcsts/article/view/11295"
---

# Fine-Tuning MARBERT for Sentiment Analysis in Jordanian Arabic Dialects Using a Synthetic Dialectal Corpus

- Authors: H. Al Drous and colleagues
- Year: 2025
- Venue: Journal of Computer Science and Technology Studies, volume 7, number 11, pages 373-386

## What they did

They fine-tuned MARBERT for sentiment analysis on Jordanian Arabic dialect, using a small synthetic dialectal corpus. The study is notable for showing what a dialect-specific MARBERT fine-tune can do with very little data, and for its preprocessing findings.

## Model

MARBERT, fine-tuned with the MARBERT tokenizer. Preprocessing included noise reduction and removal of symbols and useless characters. The authors report that removing symbols is not important, while over-repetition and noise reduction matter.

## Dataset

A collected set of 900 social media samples in Jordanian Arabic, 300 per sentiment class.

## Results

- F1 score of 0.88 on the Jordanian dialect sentiment task

## Lesson for SVR

Two lessons, one encouraging and one cautionary. The encouraging one is that MARBERT fine-tuned on only 900 dialectal samples reaches 0.88 F1, which suggests our 4,031 training rows are enough for a solid fine-tune, and that our rare classes will suffer from data size rather than from the model family. The caution is that 900 samples with three balanced classes is a small and easy setup, so 0.88 F1 should not be read as an expected score for our imbalanced 9-class task. The preprocessing finding is directly usable: light preprocessing (noise reduction, repeated-character handling) helps, while aggressive symbol stripping does not, which matches the lesson from other Arabic work that heavy preprocessing destroys dialectal cues. For our Whisper transcripts, the equivalent rule is to normalize lightly and keep the words as spoken.

## Source

https://alkindipublishers.org/index.php/jcsts/article/view/11295
