---
title: "GradNorm: gradient normalization for adaptive loss balancing in multi-task learning"
tags: [multi-task-learning, loss-weighting, GradNorm, gradient-balancing]
source_url: "https://arxiv.org/abs/1711.02257"
---

# GradNorm: gradient normalization for adaptive loss balancing in multi-task learning

## What it is

GradNorm (Chen, Badrinarayanan, Lee and Rabinovich, ICML 2018, arXiv:1711.02257) balances multi-task training by dynamically tuning gradient magnitudes. Instead of weighting losses by their values, it weights them so that the gradient norms of the different tasks stay balanced at the shared layers. It targets the actual mechanism of task dominance: one task producing much larger gradients than the others and taking over the shared encoder.

## How it works

During training, GradNorm measures the gradient norm of each task loss with respect to the shared layers. It defines a target gradient norm for each task based on the task's relative training speed (its loss relative to its initial loss). A separate GradNorm loss penalizes the difference between the actual and target gradient norms, and the task weights are updated by gradient descent on that GradNorm loss. Tasks that are training too fast get their weight reduced; tasks that lag get their weight increased. The method has a single hyperparameter, alpha, which controls how strongly the weights push lagging tasks to catch up. Reported values used are alpha 0.1 to 0.5 in the literature.

## Reported results

The paper reports that GradNorm improves accuracy and reduces overfitting across multiple tasks compared with single-task networks, static baselines and other adaptive loss balancing techniques, on synthetic and real datasets, for regression and classification. It also matches or surpasses exhaustive grid search over fixed weights, while needing only a few training runs regardless of the number of tasks.

A later study on 128 PubChem BioAssay tasks (Loss-Balanced Task Weighting, AAAI 2019) compared methods directly: mean PR AUC was 0.232 for single-task learning, 0.241 for plain multi-task learning, 0.239 for GradNorm with alpha 0.1 and 0.189 for GradNorm with alpha 0.5; mean ROC AUC was 0.799 single-task, 0.857 plain multi-task, 0.806 and 0.840 for the two GradNorm settings. GradNorm cut the number of tasks suffering negative transfer from 98 (plain multi-task) to 46 (alpha 0.1) and 47 (alpha 0.5), so its main value there was preventing harm rather than raising the average. In a separate retrieval study, GradNorm performed slightly better than the naive no-adaptation baseline (72.66 percent vs 72.47 percent average R-precision), a small gain.

## Assessment for SVR

GradNorm is a solid second option behind uncertainty weighting. Its strength is directly controlling gradient magnitudes, which is the failure mode we fear: the 9-class category head and the frequent classes could dominate the shared encoder while churn starves. Its weakness is cost and complexity: it needs an extra backward pass per task to measure gradient norms, an extra optimizer for the weights, and tuning of alpha. With only four tasks and one small dataset, uncertainty weighting gives most of the benefit with one scalar per task and no extra backward passes. Use GradNorm only if uncertainty weighting still shows one task dominating or if a task's validation score drops below its single-task baseline.
