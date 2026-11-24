---
title: "Hugging Face Trainer guide for fine-tuning BERT"
tags: [training, hyperparameters, huggingface, trainer, fine-tuning, svr]
source_url: "https://huggingface.co/learn/nlp-course/chapter3/3"
---

# Hugging Face Trainer guide for fine-tuning BERT

Source: Hugging Face NLP Course, Chapter 3, "Fine-tuning a model with the Trainer API" (https://huggingface.co/learn/nlp-course/chapter3/3). Checked November 2026.

## What the guide teaches

The Trainer class handles fine-tuning of any pre-trained model with modern best practices. The workflow is: define TrainingArguments, load the model with AutoModelForSequenceClassification, build a Trainer with train and eval datasets plus a data collator, call trainer.train(), and evaluate with a compute_metrics function. Evaluation during training needs eval_strategy set to "epoch" or "steps" plus a compute_metrics function, otherwise only training loss is reported.

## Concrete values shown in the guide

| Hyperparameter | Guide value |
|---|---|
| Learning rate | 2e-5 (used in the worked examples, including the scheduler example) |
| Scheduler | Linear decay by default; cosine is shown as an alternative via lr_scheduler_type="cosine" |
| Evaluation | eval_strategy="epoch" |
| Mixed precision | fp16=True for faster training and lower memory use |
| Gradient accumulation | Example: per_device_train_batch_size=4 with gradient_accumulation_steps=4, giving an effective batch size of 16 |
| Metrics | compute_metrics built on the evaluate library; the MRPC example reports accuracy and F1 |

The guide says the TrainingArguments defaults "should work pretty well for a basic fine-tuning", but it does not publish a full default table in this chapter. The worked examples consistently use learning rate 2e-5, which matches the BERT paper's middle value.

## Trainer defaults the team must set explicitly

These defaults in the Transformers Trainer are easy to miss and matter for SVR:

- weight_decay defaults to 0.0 in TrainingArguments, not 0.01. Set weight_decay=0.01 explicitly to match the BERT and RoBERTa papers.
- warmup_ratio defaults to 0.0. Set warmup_ratio=0.1 explicitly (BERT) or 0.06 (RoBERTa).
- lr_scheduler_type defaults to "linear", which matches both papers. Keep it.
- adam_beta1 defaults to 0.9, adam_beta2 to 0.999, adam_epsilon to 1e-8. These match the BERT paper. Keep them.
- max_grad_norm defaults to 1.0. Keep it.
- logging_steps defaults to 500, which is too coarse for 4,031 rows (about 252 steps per epoch at batch size 16). Set logging_steps to 25 or 50 so training loss is visible within each epoch.
- save_strategy and eval_strategy should both be "epoch" so a checkpoint exists per epoch and early stopping can pick the best one.
- load_best_model_at_end must be set to True together with EarlyStoppingCallback, otherwise training returns the last checkpoint instead of the best one.
- seed defaults to 42. Change it per run for the multi-seed protocol (for example 42, 1337, 2023, 7, 99).

## Assessment for SVR

Use the Trainer as the training harness and set every hyperparameter explicitly rather than relying on defaults. The two defaults that would silently hurt SVR are weight_decay 0.0 and warmup_ratio 0.0. For a multi-task model the team needs a custom Trainer subclass or a custom compute_loss, because the stock Trainer assumes one label column and one loss; the guide's single-task setup does not cover that. The guide's gradient accumulation example is directly useful if GPU memory forces a small per-device batch: per-device batch 8 with 2 accumulation steps gives the recommended effective batch size of 16.
