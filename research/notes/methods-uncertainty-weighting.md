---
title: "Uncertainty weighting for multi-task loss balancing (Kendall et al. 2018)"
tags: [multi-task-learning, loss-weighting, uncertainty-weighting, Kendall]
source_url: "https://arxiv.org/abs/1705.07115"
---

# Uncertainty weighting for multi-task loss balancing (Kendall et al. 2018)

## What it is

Kendall, Gal and Cipolla (2018, CVPR, arXiv:1705.07115) proposed weighting each task loss by the homoscedastic uncertainty of that task. Homoscedastic uncertainty is a per-task noise level that stays constant across inputs but differs between tasks. Instead of hand tuning fixed weights, the model learns one log-variance parameter per task during training.

## How it works

The total loss is the sum over tasks of a weighted task loss plus a regularization term:

Loss = sum over tasks of [ 1 / (2 * sigma_i^2) * L_i + log(sigma_i) ]

Each task i has a learnable uncertainty sigma_i. The loss for task i is scaled down by 1 / (2 * sigma_i^2), so noisy or hard tasks contribute less to the total loss. The log(sigma_i) term stops the weights from collapsing to zero. In practice the model learns log(sigma_i) as a free parameter, initialized at zero, and the weighting adapts automatically as training proceeds. The method works for both regression and classification losses and for tasks with different units and scales.

## Reported results

The original paper applied it to per-pixel depth regression, semantic segmentation and instance segmentation from a single image. The multi-task model with learned uncertainty weights outperformed separate models trained individually on each task, which is the result a naive fixed-weight multi-task model often fails to reach. The paper reports that hand tuning the weights is difficult and expensive, and that the learned weighting removes that search.

A 2026 application to joint named entity recognition and text classification on disaster tweets (HUMAID-NER, arXiv:2609.16964) shows the same mechanism fixing a concrete failure: under fixed task weights, the token-level NER loss dominated and classification macro-F1 fell 1.4 points across epochs. Homoscedastic uncertainty weighting with learnable per-task log-variance parameters resolved the conflict. Combined with a two-stage schedule that froze the lower 18 of 24 encoder layers in stage two, the joint RoBERTa-large model reached NER span micro-F1 of 0.841 and classification macro-F1 of 0.761, matching or beating dedicated single-task RoBERTa-large classifiers on the same benchmark (0.730 to 0.750).

## Recommended settings

Initialize each log-variance parameter at 0. Let the optimizer update them together with the model weights. No grid search over task weights is needed. Combine with a two-stage schedule when tasks differ strongly in gradient density: train all layers jointly first, then freeze the lower encoder layers and let the heads specialize.

## Assessment for SVR

This is our top candidate loss weighting scheme. Our four tasks are all classification, but their loss scales differ: the 9-class category loss is naturally larger than the binary churn loss, and churn has only 32 positive rows, so a fixed equal weighting would let category dominate and churn underfit. Uncertainty weighting adapts per task without a weight search, which fits our setup because the team trains the model and we only select hyperparameters. It is cheap to implement (one scalar parameter per head) and has a direct published precedent of rescuing a classification head that fixed weights were starving. Start with equal weights as a baseline, then compare against uncertainty weighting on validation macro-F1 per task, especially churn recall.
