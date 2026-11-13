---
title: "Text data augmentation for minority classes on small datasets"
tags: [class-imbalance, data-augmentation, EDA, back-translation, small-dataset]
source_url: "https://hal.science/hal-05090101v3/document"
---

# Text data augmentation for minority classes on small datasets

## What it is

Data augmentation creates new training examples by transforming existing ones while preserving the label. For text, the main families are lexical, semantic and generative. Lexical methods change the surface form: Easy Data Augmentation (EDA, Wei and Zou, 2019) applies four random operations, synonym replacement, random insertion, random swap and random deletion, at a small rate (about 10 percent of words). Semantic methods paraphrase: back-translation translates a sentence into another language and back, producing a different wording with the same meaning. Contextual augmentation replaces a word with a prediction from a masked language model, which fits the context better than a dictionary synonym. Generative augmentation uses a large language model to write new examples in the style of the minority class.

## Reported results

A 2026 comparison of augmentation methods for small-dataset sentiment classification (Mayaleh and Mayaleh, Discover Artificial Intelligence) found that all three methods improve performance, that contextual augmentation gives the most consistent gains for BERT models, and that EDA and back-translation give greater benefits for traditional classifiers. The same study reports LLM-generated data raising macro-F1 from 0.45 to 0.76 on a small text classification task. A study on student perceptions of generative AI used a hybrid of EDA, back-translation and generative augmentation targeted at the minority class (negative sentiment, 7.5 percent of data) and raised accuracy from 65.00 percent to 79.07 percent and weighted F1 to 73.90 percent, though a substantial share of minority samples was still misclassified. A Hinglish sarcasm study combined EDA, synonym replacement and back-translation and reached about 95 percent F1 on a 5,250 tweet dataset with a 9.6 percent minority class. The Tamil political sentiment system used LLM augmentation with Gemini 2.5 Flash to expand training data from 4,352 to 15,316 samples (3.5 times), cutting the imbalance ratio from 8:1 to 4:1, and reached 35.79 percent macro-F1 on dev, a 67 percent relative improvement over the non-augmented baseline.

## Recommended settings

For EDA, use the original paper's rates: change about 10 percent of words per operation and generate 4 to 16 augmented sentences per original for small datasets, but validate that the label still holds. For back-translation, one pivot language is usually enough; Arabic to English and back is the natural pair for our transcripts, or Arabic to French and back for variety. For contextual augmentation, replace one or two tokens per sentence with a masked language model prediction. For generative augmentation, prompt the model with several real minority examples and ask for new ones in the same style, then have a human spot-check that the label still applies. Always augment the training split only, and keep a clean unaugmented validation set so gains are real.

## Assessment for SVR

Augmentation is the only method that adds genuinely new information about churn instead of reweighting the same 22 rows, so it is the most promising complement to class weights. The risk is label drift: a paraphrase of a churn voicemail can easily stop sounding like churn, and Egyptian Arabic dialect makes synonym replacement and back-translation less reliable than in English, because dialect words often have no clean synonym and machine translation normalizes dialect into standard Arabic. Contextual augmentation with an Arabic BERT and LLM paraphrasing with dialect-preserving prompts are the two best bets, both followed by human review of every augmented churn example, which is feasible because the class is tiny. A realistic target is expanding churn from 22 training rows to 100 to 200 reviewed variants. Test augmentation only for churn and mad, not for the whole dataset, so the majority classes are not distorted.
