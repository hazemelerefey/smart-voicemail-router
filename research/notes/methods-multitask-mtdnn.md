---
title: "Multi-task learning for text classification: MT-DNN and hard parameter sharing"
tags: [multi-task-learning, text-classification, MT-DNN, BERT, hard-sharing]
source_url: "https://www.chriswirz.com/reviews/multi-task-deep-neural-networks-mt-dnn-nlu/index.html"
---

# Multi-task learning for text classification: MT-DNN and hard parameter sharing

## What it is

Multi-task learning (MTL) trains one model on several related tasks at the same time so the tasks share knowledge and regularize each other. The standard architecture is a shared backbone encoder that turns the input into a common representation, followed by one small task-specific head per task. Gradients from every task loss flow back through its own head and then jointly through the shared backbone.

MT-DNN (Multi-Task Deep Neural Network, Liu, He, Chen and Gao, Microsoft, 2019, arXiv:1901.11504) is the reference design for text classification. Its lower layers, a lexicon encoder and a multi-layer bidirectional Transformer encoder, are initialized from a pretrained BERT and shared by all tasks. Each task gets its own output layer: a softmax for single-sentence classification, a linear score for text similarity, a stochastic answer network for pairwise classification, and a pairwise ranking loss for question answering.

## Hard vs soft parameter sharing

Hard parameter sharing shares the hidden layers between all tasks and keeps only task-specific output layers. It is the most common approach in deep learning MTL and the one MT-DNN uses. Soft parameter sharing gives each task its own model and regularizes the parameters to stay similar, for example with an L2 penalty on the distance between task-specific weights. Soft sharing costs far more parameters and is rarely used with large pretrained transformers. For a pretrained encoder such as BERT, hard sharing is the practical default: one encoder, four classification heads.

## How training works in MT-DNN

Mini-batches from the different tasks are merged and shuffled. Each batch updates the shared encoder and its own task head using only that task's loss. After multi-task training, the model is fine-tuned separately on each task. Training used Adamax with learning rate 5e-5, batch size 32, up to 5 epochs, linear decay with 10 percent warm-up, task-specific dropout (0.1, except 0.3 for MNLI and 0.05 for CoLA), and gradient clipping at norm 1.

## Reported results

On the GLUE benchmark, MT-DNN reached a score of 82.7 against 80.5 for BERT-large, a gain of 2.2 points, with new state of the art results on eight of nine GLUE tasks. Without the per-task fine-tuning step it still scored 81.7. The largest gains came on the tasks with the smallest datasets: RTE rose from 71.1 (BERT) to 83.4 (MT-DNN) on the dev set, and CoLA from 60.5 to 62.5 on test. The paper also reports that the MT-DNN representation adapts to new tasks with fewer labels than BERT.

## Assessment for SVR

This is the closest published template to our setup. Our four labels are four classification tasks over the same input text, which is exactly the single-sentence classification case in MT-DNN. Recommended design: one pretrained encoder (Arabic-capable BERT such as CAMeLBERT or MARBERT), one linear softmax head per label, joint training with shuffled mixed batches, then optional per-head fine-tuning. The literature says the small-data task benefits most, which matters for us because churn has only 32 positive rows: its head can borrow representation signal from the other three tasks. The main risk is negative transfer, where one task hurts another, so we should compare the multi-task model against single-task baselines per label and keep the per-task fine-tuning step.
