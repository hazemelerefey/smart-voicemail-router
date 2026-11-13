---
title: "RoBERTa paper fine-tuning recipe (Liu et al. 2019)"
tags: [training, hyperparameters, roberta, fine-tuning, svr]
source_url: "https://arxiv.org/abs/1907.11692"
---

# RoBERTa paper fine-tuning recipe (Liu et al. 2019)

Source: Liu, Ott, Goyal, Du, Joshi, Chen, Levy, Lewis, Zettlemoyer, Stoyanov, "RoBERTa: A Robustly Optimized BERT Pretraining Approach", arXiv:1907.11692. Values below come from Section 5.1 and Appendix C of the paper.

## What RoBERTa changes relative to BERT

RoBERTa is a replication study of BERT pre-training. Its changes are: training longer with bigger batches over more data, removing the next sentence prediction objective, training on longer sequences, and dynamically changing the masking pattern. The fine-tuning procedure itself stays close to BERT, with a lower learning rate range and a longer epoch budget plus early stopping.

## Recommended values for GLUE fine-tuning (Section 5.1)

| Hyperparameter | RoBERTa paper value |
|---|---|
| Batch size | 16 or 32 |
| Learning rate | 1e-5, 2e-5, or 3e-5 |
| Warmup | Linear warmup for the first 6 percent of steps, followed by linear decay to 0 |
| Number of epochs | 10, with early stopping based on each task's evaluation metric on the dev set |
| Optimizer | AdamW, beta1 0.9, beta2 0.999, epsilon 1e-6, decoupled weight decay 0.01 |
| Model selection | Best hyperparameters picked from the median of 5 random seeds per task |

Note the contrast with BERT: RoBERTa drops 5e-5 from the learning rate sweep, uses a shorter warmup (6 percent instead of 10 percent), and trains up to 10 epochs but stops early on dev performance instead of fixing 2 to 4 epochs. The paper reports results as the median over five random initializations, not the best single run.

## Pre-training hyperparameters (for reference only)

Peak learning rate 4e-4 for RoBERTa-LARGE and 6e-4 for RoBERTa-BASE, batch size 8k sequences, beta2 0.98 for stability at large batch sizes. These are pre-training values and do not apply to fine-tuning.

## Assessment for SVR

RoBERTa's recipe is the better template for SVR than BERT's fixed 2 to 4 epochs, because it pairs a low learning rate with early stopping instead of a fixed epoch count. For SVR, use learning rate 2e-5 as the starting point with a sweep over 1e-5, 2e-5, 3e-5, batch size 16, warmup ratio 0.06 to 0.1, weight decay 0.01, and a maximum of 5 epochs with early stopping on validation macro-F1 (patience 2 epochs). The 10 epoch budget in the paper fits GLUE tasks with more data and a dev set per task; on 4,031 training rows, 5 epochs with early stopping gives the same protection against under-training without inviting overfitting. Follow the paper on seeds: run 5 seeds and report the median or mean plus standard deviation, never a single best run.
