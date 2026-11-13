---
title: "BERT paper fine-tuning recipe (Devlin et al. 2019)"
tags: [training, hyperparameters, bert, fine-tuning, svr]
source_url: "https://arxiv.org/abs/1810.04805"
---

# BERT paper fine-tuning recipe (Devlin et al. 2019)

Source: Devlin, Chang, Lee, Toutanova, "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding", arXiv:1810.04805 (NAACL 2019). Values below come from Section 4 and Appendix A.3 of the paper, verified against the full text.

## What fine-tuning means in the paper

Fine-tuning loads the pre-trained parameters, adds one task-specific output layer, and trains all parameters end to end on the labeled downstream data. No task-specific architecture is needed beyond the output layer. For classification, the final hidden state of the [CLS] token feeds the classifier.

## Recommended values from Appendix A.3

The paper states these ranges work well across all tasks. It recommends an exhaustive search over them and selecting the best model on the development set.

| Hyperparameter | BERT paper value |
|---|---|
| Batch size | 16 or 32 |
| Learning rate (Adam) | 2e-5, 3e-5, or 5e-5 |
| Number of epochs | 2, 3, or 4 |
| Dropout probability | 0.1, always kept |
| Warmup | Learning rate warmed up over the first 10 percent of steps, then linearly decayed (Section 3.2 and Appendix A.1 describe this schedule for pre-training; the same schedule is used for fine-tuning) |
| Optimizer | Adam, beta1 0.9, beta2 0.999, L2 weight decay 0.01 |
| Max sequence length | 128 tokens for most GLUE tasks (512 for SQuAD style tasks) |

Task-specific values the paper actually used: GLUE tasks used batch size 32 and 3 epochs, with the learning rate picked per task from 5e-5, 4e-5, 3e-5, 2e-5 on the dev set. SQuAD used 3 epochs, learning rate 5e-5, batch size 32. SWAG used 3 epochs, learning rate 2e-5, batch size 16.

## Small datasets

The paper states explicitly that large datasets (100k plus labeled examples) are far less sensitive to hyperparameter choice than small datasets. Small datasets need the search above, not a single guess. For BERT-LARGE the authors found fine-tuning was sometimes unstable on small datasets, so they ran several random restarts and selected the best model on the development set. This instability note matters for SVR: our training set is 4,031 rows, which is small by the paper's standard.

## Assessment for SVR

The BERT recipe is the baseline every later guide copies. For SVR, start at the middle of the paper's ranges: learning rate 2e-5, batch size 16, 3 epochs, warmup 10 percent, weight decay 0.01, dropout 0.1, AdamW. Sweep learning rate over 1e-5, 2e-5, 3e-5 and epochs 2 to 4, selecting on validation macro-F1. Do not use 5e-5 as the starting point on a 4,031 row dataset: the paper's own instability warning and later work both point to the lower end for small data. Max sequence length 128 is enough for voicemail transcripts, but confirm from the token length distribution first; raise to 256 only if the 99th percentile exceeds 128.
