---
title: "Class weights, oversampling and undersampling for imbalanced text classification"
tags: [class-imbalance, class-weights, oversampling, undersampling, text-classification]
source_url: "https://jurnal.polibatam.ac.id/index.php/JAIC/article/download/13686/3889"
---

# Class weights, oversampling and undersampling for imbalanced text classification

## What they are

Class weights change the loss so that errors on rare classes cost more. The standard formula is weight for class c = total samples / (number of classes * samples in class c). This is the sklearn class_weight = balanced rule and is already saved for SVR (churn at_risk weight 89.859, mad weight 7.234). In a neural model the weights multiply the per-example cross-entropy before averaging.

Random oversampling duplicates minority-class examples until the classes are balanced. Random undersampling deletes majority-class examples until the classes are balanced. Weighted random sampling is the batch-level version of oversampling: each training batch is sampled so minority examples appear more often, without duplicating rows in the dataset.

## How they compare

Class weights are the cheapest option: no data changes, no extra training time, one line in the loss. They work well up to moderate imbalance but a weight near 90, as ours is for churn, makes each churn example count as 90 examples, which can destabilize training and make the model overfit those 22 training rows.

Random oversampling has the same overfitting risk in a different form: the model sees the same 22 churn transcripts dozens of times per epoch and memorizes them. It is simple and often works, but it adds no new information. Weighted sampling spreads the repeats across batches and is generally preferred over hard duplication for neural models.

Undersampling throws away real data. On a small dataset of 5,751 rows it is the weakest option, because the majority classes still need their examples to learn the other three tasks, and our tasks share one encoder. Never undersample in a multi-task setting where the majority class of one task is the training signal for another.

## Reported results

Indonesian cyberbullying detection with IndoBERTweet-BiGRU (JAIC, 2026): class weights raised macro-F1 from 0.80 at baseline to 0.89 after the label set was made less skewed; random oversampling reached macro-F1 0.89 with accuracy 0.93; focal loss reached 0.90. On Tokopedia reviews, class weights and focal loss together improved performance by about 2 to 11 percent over baseline. The Tamil political sentiment system combined focal loss (gamma 3.0) with weighted sampling and LLM augmentation for a 67 percent relative macro-F1 improvement over baseline.

## Recommended settings

Start with class weights using the balanced formula, already computed for SVR, and cap the maximum weight. A common cap is 10 to 20, or the square root of the balanced weight, to avoid letting 22 rows dominate the loss. Compare three variants on validation macro-F1 per task: (1) class weights as saved, (2) capped class weights, (3) weighted random sampling with no loss weights. Keep the split stratified and apply any resampling to the training split only, never before splitting, or validation scores will leak.

## Assessment for SVR

Class weights are the baseline we should keep: they are already computed, they cost nothing, and the literature shows they reliably add several macro-F1 points. The open question is the cap, because a weight of 89.859 on 22 training rows is extreme and risks memorization. Treat capped weights and weighted sampling as the two serious alternatives to test. Do not undersample. Oversampling by duplication is acceptable only for the churn head if combined with augmentation that creates genuinely new variants of those rows.
