---
title: "Fine-tuning instability on small datasets (Mosbach et al. 2021)"
tags: [training, fine-tuning, stability, small-dataset, bert, svr]
source_url: "https://arxiv.org/abs/2006.04884"
---

# Fine-tuning instability on small datasets (Mosbach et al. 2021)

Source: Mosbach, Andriushchenko, Klakow, "On the Stability of Fine-tuning BERT: Misconceptions, Explanations, and Strong Baselines", arXiv:2006.04884, accepted at ICLR 2021. Verified against the arXiv HTML version.

## The finding

Fine-tuning BERT, RoBERTa, and ALBERT is unstable: training the same model with multiple random seeds can produce a large variance in task performance. The authors show that the two commonly blamed causes do not explain it: catastrophic forgetting and small dataset size both fail as explanations. Instead the instability has two parts:

1. Optimization difficulties early in training, characterized by vanishing gradients in the first steps.
2. Differences in generalization late in training: runs with almost identical training loss show noticeably different test performance.

The instability was observed for BERT-LARGE and RoBERTa-LARGE and ALBERT-LARGE. The authors did not observe it for BERT-BASE. SVR will most likely use a base-size Arabic encoder (MARBERT is BERT-base size, 163M parameters), which is reassuring, but the variance warning still applies because SVR has only 4,031 training rows and a rare class with 32 rows.

## The recommended baseline from the paper

- Use small learning rates with Adam bias correction enabled. The paper's analysis used learning rate 2e-5 with linear warmup over the first 10 percent of steps and linear decay to 0, with AdamW without bias correction as the unstable reference setup. Turning bias correction on is part of the fix.
- Train for considerably more iterations than the usual 3 epochs, until training loss is close to zero. Longer training with a small learning rate stabilizes the runs.
- Report the spread over several seeds, not only the best seed. The RoBERTa paper already reports the median of 5 seeds; Mosbach et al. use up to 25 seeds in their analysis.

## Practical rules for SVR

1. Never trust a single fine-tuning run. Run at least 5 seeds (42, 1337, 2023, 7, 99) for every configuration that is compared, and report mean plus standard deviation of macro-F1 per task.
2. Keep Adam bias correction enabled. The Hugging Face Trainer default optimizer (adamw_torch) applies bias correction; do not switch it off.
3. Use learning rate 2e-5 as the starting point, not 5e-5. Higher learning rates are a key driver of the early optimization failures.
4. Allow up to 5 epochs with early stopping on validation macro-F1 (patience 2 epochs) instead of fixing 3 epochs. This follows both Mosbach (train longer, small learning rate) and RoBERTa (early stopping on dev metric), while the early stopping guard prevents the extra epochs from overfitting a 4,031 row dataset.
5. Watch gradient norms in the first 50 steps. Vanishing gradients early are the signature of a failed run; a run that collapses early will not recover.
6. Select models on validation data only. The test set (584 rows) is touched once, at the end, for the final report.
7. Expect variance on the rare classes. With 32 at-risk churn rows in total, seed variance on churn recall will be large. Report the mean plus standard deviation across seeds for churn, and do not let a lucky seed decide the configuration.

## Assessment for SVR

This paper is the strongest reason SVR needs a multi-seed protocol and a low learning rate. A single run that scores well on churn could be luck, and a single run that scores badly could be a failed optimization rather than a bad model. Budget for 5 seeds per configuration in the experiment plan. The cost is small: 4,031 rows at batch size 16 is about 252 steps per epoch, so a 3 to 5 epoch run finishes in minutes on a single GPU.
