---
title: "Focal loss for imbalanced text classification"
tags: [class-imbalance, focal-loss, text-classification, BERT, minority-class]
source_url: "https://jurnal.polibatam.ac.id/index.php/JAIC/article/download/13686/3889"
---

# Focal loss for imbalanced text classification

## What it is

Focal loss (Lin et al., 2017, arXiv:1708.02002) reshapes cross-entropy so that easy, well-classified examples contribute almost nothing to the loss and hard examples dominate. It adds a modulating factor to cross-entropy:

Focal loss = - alpha_t * (1 - p_t)^gamma * log(p_t)

Here p_t is the model's predicted probability for the true class, gamma is the focusing parameter, and alpha_t is an optional per-class weight. When an example is easy (p_t near 1), the factor (1 - p_t)^gamma shrinks its loss toward zero. When it is hard or misclassified, the factor stays near 1 and the loss behaves like cross-entropy. The effect is that the majority class, which the model learns to classify easily early on, stops swamping the gradient, and the minority class keeps getting training signal.

## Recommended settings

The standard starting point from the original paper is gamma = 2.0 and alpha_t set inversely proportional to class frequency. Recent text classification work uses gamma 2.0 to 3.0. A 2026 shared-task system on Spanish gender-based violence reports used focal loss with gamma = 2, per-class alpha weights inversely proportional to class frequency, and label smoothing epsilon = 0.05 for a 4-class severity task where the rarest class was about 5 percent of samples (WomenHelp 2026, CEUR-WS). A Tamil political sentiment system used gamma = 3.0 with weighted sampling on a 7-class task with an 8:1 imbalance ratio. Label smoothing is a useful companion because focal loss can otherwise push the model toward overconfident predictions on the few minority examples.

## Reported results

Indonesian cyberbullying detection with IndoBERTweet-BiGRU (JAIC, 2026) compared methods on the same data: with the original imbalanced label set, focal loss gave macro-F1 0.79, the lowest of the tested methods, because the rarest classes had only hundreds of instances and the model could not learn representative patterns from so few samples. After merging two rare classes so the minority had thousands of samples, focal loss reached macro-F1 0.90, accuracy 0.93, precision 0.90 and recall 0.90, the best result in the study. In the same study, class weights raised macro-F1 from 0.80 (baseline) to 0.89, and random oversampling reached 0.89. On Tokopedia customer reviews with IndoBERT and BiLSTM, applying class weights and focal loss improved performance by approximately 2 to 11 percent over the baseline. The Tamil system combining LLM augmentation with focal loss (gamma 3.0) and weighted sampling reached 35.79 percent macro-F1 on dev, a 67 percent relative improvement over the non-augmented baseline, though the absolute score stayed low because the task is hard. In the WomenHelp 2026 system, per-label threshold optimization added a further absolute macro-F1 gain of 0.017 on the dev set on top of focal loss.

## Assessment for SVR

Focal loss is worth testing for churn and for the mad state class, but it is not a cure for 32 rows. The Indonesian study is the cautionary result: with only hundreds of minority examples focal loss was the worst method, and it only won after the minority class was enlarged. Our churn class has 32 rows in the full set and about 22 in train, far below that threshold, so focal loss alone will not teach the model what churn sounds like. Use it as one candidate head loss for churn, with gamma 2.0 and alpha from inverse frequency, and compare against plain class-weighted cross-entropy on validation. Combine it with threshold tuning on the validation set rather than expecting the loss alone to fix recall. Do not use it as the only imbalance method.
