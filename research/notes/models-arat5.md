---
title: "AraT5 and AraT5v2 - Arabic Text to Text Transformer"
tags: [svr, models, arabic-nlp, text-classification, arat5, t5]
source_url: "https://huggingface.co/UBC-NLP/AraT5v2-base-1024"
---

# AraT5 and AraT5v2

## What it is

AraT5 is an Arabic version of T5, the text to text transformer, from the University of British Columbia NLP group, Nagoudi et al. 2021 and 2022. It is an encoder decoder model: it reads text and generates text. Classification is done by generating the label as text, for example by training it to output "positive" or a category name. AraT5v2 is the improved second version.

## Hugging Face

- Model ID: `UBC-NLP/AraT5v2-base-1024`
- Link: https://huggingface.co/UBC-NLP/AraT5v2-base-1024
- First version: `UBC-NLP/AraT5-base`
- Link: https://huggingface.co/UBC-NLP/AraT5-base

## Size

- AraT5v2 base: about 220M parameters.
- AraT5 base: about 220M parameters.
- AraT5v2 increases the maximum sequence length from 512 to 1024 tokens, and supports 100 sentinel tokens.

## Training data

- Pretrained on large scale MSA and dialectal Arabic corpora, including AraNews, El-Khair, and OSCAR.
- AraT5v2 was trained on a larger and more diverse Arabic dataset than AraT5, including Twitter data, which gives it dialect exposure.
- The authors report that AraT5v2 converges about 10 times faster than AraT5.

## Classification performance

- AraT5 was evaluated on the ARGEN benchmark for Arabic generation and understanding. It is strong on generation tasks such as summarization, translation, and question generation.
- For classification, it can be fine tuned as a text to text classifier and has been used for hate speech detection and sentiment analysis in dialectal Arabic. One hate speech study fine tuned AraT5v2-base-1024 with batch size 16, learning rate 3e-5, and 4 epochs.
- It is not the usual first choice for pure classification. Encoder only models such as MARBERTv2 and EgyBERT give a direct classification head, faster training, and simpler multi task learning with four label heads. AraT5 adds a decoder that SVR does not need for classification.

## Egyptian dialect coverage

- Partial. The training data includes dialectal Arabic and Twitter data, and the dialect to MSA translation work built on AraT5v2 covers Egyptian among five dialects, but it is not Egyptian specific.

## Assessment for SVR

- Strengths: strong Arabic generation, useful if SVR later needs to generate a ticket summary or a normalized MSA version of a transcript. The 1024 token context helps with long voicemails.
- Weaknesses: encoder decoder is heavier and slower to fine tune than a BERT encoder for the same classification job, and text to text classification is awkward for four simultaneous labels with severe imbalance.
- Verdict: do not use as the main classifier. Keep it as a candidate for a later generation step, for example drafting the callback ticket text, and for dialect to MSA normalization if the team tests that as a preprocessing step.

## Source

- Model card: https://huggingface.co/UBC-NLP/AraT5v2-base-1024
- Paper: Nagoudi et al. 2022, AraT5v2.
