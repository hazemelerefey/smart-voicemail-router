---
title: "SMOTE for text data: why it does not apply to raw text"
tags: [class-imbalance, SMOTE, text-classification, embeddings, oversampling]
source_url: "https://aiwiki.ai/wiki/oversampling"
---

# SMOTE for text data: why it does not apply to raw text

## What it is

SMOTE (Synthetic Minority Over-sampling Technique, Chawla et al., 2002, Journal of Artificial Intelligence Research, volume 16, pages 321-357) creates synthetic minority examples by interpolating between a minority sample and one of its k nearest neighbors in feature space: new_sample = sample + rand(0,1) * (neighbor - sample). It was designed for continuous numerical features, typically tabular data.

## Why it does not apply to raw text

Text is discrete. Tokens are integer ids, not points in a continuous space, so interpolating between two token sequences produces no valid sentence. Averaging two word ids gives a third id that means something unrelated, and averaging two sequences of different lengths is undefined. Standard SMOTE operates only on continuous numerical features and cannot handle categorical or mixed data directly. Variants such as SMOTE-NC exist for mixed tabular data, but they do not solve the discrete-text problem.

## Where SMOTE can be used for text

SMOTE can be applied after text is converted to dense vectors: TF-IDF vectors, or BERT CLS embeddings, or sentence embeddings. In that case the interpolation happens in embedding space and the synthetic point is fed to a classifier that accepts vectors, such as an SVM or a linear head on frozen embeddings. It cannot be applied inside an end-to-end fine-tuning pipeline, because the model input is token ids, not embeddings, and there is no way to decode a synthetic embedding back into a real transcript.

A 2025 study in Scientific Reports benchmarked 31 SMOTE-based oversampling techniques on text classification datasets using transformer-based vectorization (MiniLMv2) on the TREC and Emotions datasets, and found that the best technique depends on the dataset and the classifier used. There is no single SMOTE variant that wins for text. A 2026 study on Indonesian tourism reviews used frozen IndoBERT embeddings with PCA dimensionality reduction and SMOTE inside a strict cross-validation pipeline feeding an SVM, and reported that it significantly outperformed traditional baselines on highly imbalanced low-resource text. A 2026 enterprise profiling paper applied SMOTE in the dense semantic space (TF-IDF plus BERT embeddings) paired with focal loss and reached macro-F1 95.4 percent on about 50,000 enterprises. Practical guidance from recent guides: reduce dimensions with PCA or truncated SVD before SMOTE on BERT embeddings, tune k_neighbors in the range 3 to 10, use Borderline-SMOTE or ADASYN for boundary and hard examples, and apply SMOTE only to training folds, never before splitting.

## Reported results

Guides summarizing the 2025 benchmarks report that SMOTE boosts minority-class performance by 10 to 30 percent in F1 on imbalanced text tasks and outperforms random oversampling by introducing variability. The Indonesian review study had to merge three extreme minority classes (fear, surprise, disgust) into one OTHER class before SMOTE could be applied at all, because SMOTE needs enough minority samples to find neighbors, and it still showed erratic performance on the merged class. SMOTE also risks generating noisy synthetic samples when the minority class overlaps the majority class, because interpolation near the boundary can land in majority territory.

## Assessment for SVR

Do not use SMOTE in our main pipeline. We fine-tune a transformer end to end on token ids, so there is no embedding-space step where SMOTE could run. It is only usable if we build a secondary baseline with frozen embeddings and a classical classifier, which is not our model. Even there, churn has about 22 training rows, and k nearest neighbors on 22 points in a 768-dimensional space is unreliable. The literature consensus is that for text with a transformer, the effective replacements for SMOTE are class weights, focal loss, weighted sampling, data augmentation that creates real new text, and threshold tuning. If the team wants a SMOTE experiment, restrict it to a frozen-embedding SVM baseline for comparison, not to the main model.
