---
title: "MTBERT-Attention: An Explainable BERT Model based on Multi-Task Learning for Cognitive Text Classification"
tags: [multi-task-learning, bert, explainability, attention, svr-literature]
source_url: "https://doi.org/10.1016/j.sciaf.2023.e01799"
---

# MTBERT-Attention: An Explainable BERT Model based on Multi-Task Learning for Cognitive Text Classification

- Authors: Hanane Sebbaq and Nour-eddine El Faddouli
- Year: 2023
- Venue: Scientific African, volume 21, article e01799

## What they did

They proposed MTBERT-Attention, a model that combines multi-task learning (MTL), BERT, and a co-attention mechanism for cognitive text classification using Bloom's taxonomy. The auxiliary task improves the main task's generalization and acts as data augmentation, while the co-attention mechanism focuses the model on the important parts of the text. They also proposed an attention-based explainability framework and compared it against LIME.

## Model

MTBERT-Attention: a shared BERT encoder with multiple task heads and a co-attention layer between tasks. Explainability comes from the attention weights, with LIME used as the baseline explainer.

## Dataset

E-learning texts labeled with Bloom's taxonomy cognitive levels (learning objectives, including objectives written with ambiguous action verbs).

## Results

- Overall classification accuracy of 97.71 percent on the test set
- The model beat single-task BERT baselines on loss, F1 score, and accuracy
- The attention-based explanations beat LIME on fidelity and on computational cost

## Lesson for SVR

This is the most relevant multi-task paper for our architecture, and the most relevant explainability paper for our explainable tickets. Three lessons transfer directly. First, a shared BERT encoder with separate task heads plus an auxiliary task improves generalization, which is the same design as our four-head multi-task model, and it gives us a published precedent to cite when justifying the architecture. Second, the auxiliary task works as data augmentation, which matters for us because our rarest class (churn at_risk, 32 rows) cannot be learned from its own examples alone and must borrow signal from the other heads. Third, attention weights can serve as explanations that are cheaper and more faithful than LIME, which supports our plan to show agents why a ticket got its labels: highlighting the words the model attended to is a defensible, low-cost explanation method, provided we validate that the highlighted words make sense to a human reader.

## Source

https://doi.org/10.1016/j.sciaf.2023.e01799
