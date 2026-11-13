---
title: "Arabic Topic Detection: A Comprehensive Review of Recent Advances"
tags: [survey, review, arabic-nlp, topic-detection, text-classification, svr-literature]
source_url: "https://faculty.uobasrah.edu.iq/uploads/publications/1790086421.pdf"
---

# Arabic Topic Detection: A Comprehensive Review of Recent Advances

- Authors: Noor S. Dawood and Salma A. Mahmood
- Year: 2025
- Venue: International Journal of Computational and Experimental Science and Engineering (IJCESEN), volume 11, number 3, pages 5541-5551

## What they did

This is a survey paper reviewing recent advances in Arabic topic detection and short-text analysis. It covers the shift from rule-based and statistical methods to machine learning, deep learning, and large language models (BERT, GPT), including embeddings, topic modeling (BERTopic, LDA, NMF), and transformer fine-tuning. It gives special attention to the problems that make Arabic hard: rich morphology, complex syntax, dialectal variation, and the near-universal absence of diacritics in online text.

## Model

Surveyed models include BERT and GPT-based LLMs, AraBERT, MARBERT, and hybrid deep learning models, plus topic modeling pipelines built on UMAP, HDBSCAN, and TF-IDF.

## Dataset

The survey discusses many datasets, including Arabic taxonomy data and social media corpora. Two studies it cites are directly relevant to SVR: Mansy et al. (2022), who built an ensemble of MARBERT and AraBERT for emotion recognition on Arabic tweets (SemEval-2018 Task 1, Arabic emotion dataset), finding MARBERT better than AraBERT and the ensemble better than either alone; and Abuzayed et al. (2021), who applied BERTopic with pretrained Arabic models and found MARBERT the best performer.

## Results

The survey's conclusions, not a single experiment: transformer-based models consistently outperform traditional methods on Arabic short text; LLMs capture semantic nuance even in low-resource settings; and the main bottleneck for Arabic applications is the scarcity of high-quality, task-specific annotated datasets, especially for dialectal text. Arabic topic detection still needs better preprocessing, better classification algorithms, and more dialect-aware data.

## Lesson for SVR

As a survey, this paper is useful for orientation rather than for a single result. Three points stand out for us. First, the repeated finding that MARBERT beats AraBERT on dialectal social media text, and that an ensemble of the two beats either alone, lines up with the NADI 2024 and AHaSIS 2025 results and strengthens the case for MARBERTv2 as our starting encoder, with an AraBERT plus MARBERT ensemble as a later trial. Second, the survey names data scarcity as the central problem for Arabic NLP, which is exactly our situation: 5,751 clean rows is small, so our labeling quality, audit process, and class-weight handling matter more than squeezing the last point from the architecture. Third, the BERTopic work it cites suggests a useful diagnostic: topic modeling over our transcripts could reveal whether our 9 complaint categories match the natural clusters in the data, or whether some categories overlap and should be merged.

## Source

https://faculty.uobasrah.edu.iq/uploads/publications/1790086421.pdf
