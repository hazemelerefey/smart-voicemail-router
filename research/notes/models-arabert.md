---
title: "AraBERTv2 - Arabic BERT for Text Classification"
tags: [svr, models, arabic-nlp, text-classification, arabert]
source_url: "https://huggingface.co/aubmindlab/bert-base-arabertv2"
---

# AraBERTv2

## What it is

AraBERT is a BERT based Arabic language model from the American University of Beirut (AUB) Mind Lab, Antoun et al. 2020. AraBERTv2 is the second version. It is an encoder only transformer for classification, named entity recognition, and other understanding tasks. It is not a generative model.

## Hugging Face

- Model ID: `aubmindlab/bert-base-arabertv2`
- Link: https://huggingface.co/aubmindlab/bert-base-arabertv2
- Large version: `aubmindlab/bert-large-arabertv2`
- Twitter variant: `aubmindlab/bert-base-arabertv02-twitter`

## Size

- Base v2: about 136M parameters. Some tables list 135M. The v1 base was 110M.
- Large v2: about 371M parameters.
- Architecture: BERT base, 12 encoder layers, 768 hidden size, 12 attention heads, 512 maximum sequence length.
- Vocabulary: 60,000 WordPiece tokens. AraBERTv2 uses Farasa segmentation of words into stems, prefixes, and suffixes before subword tokenization.

## Training data

- AraBERTv1: about 24 GB of text, 70 million sentences, from Arabic news, the 1.5B words Arabic Corpus, and OSIAN.
- AraBERTv2: about 77 GB of text, about 200 million sentences, about 8.6B tokens. Sources are manually scraped Arabic news sites, Arabic Wikipedia, the unshuffled OSCAR corpus, the 1.5B words Arabic Corpus, OSIAN, and Assafir news.
- Mainly Modern Standard Arabic (MSA). Dialect coverage is limited. A small addition of about 12,000 dialect sentences was reported for one dialect variant, and the separate Twitter variant was pretrained on 60 million Arabic tweets in different dialects and MSA.

## Classification performance

- AraBERT was the first widely used monolingual Arabic BERT and set strong results on Arabic sentiment analysis, named entity recognition, and question answering at release.
- In newer head to head comparisons on dialectal text it now trails dialect pretrained encoders. In DialectSentEval 2026 Subtask 1, a three class sentiment task covering Moroccan, Egyptian, Jordanian, and Saudi Arabic, AraBERTv2 scored 79.77 percent macro F1, against 94.07 percent for MARBERTv2 and 81.96 percent for CAMeLBERT.
- In the MuDRiC multi dialect commonsense validation task, AraBERTv2 averaged 65.34 percent accuracy, with 68.33 percent on Egyptian, against 78.16 percent average and 80.73 percent on Egyptian for MARBERTv2.
- On MSA heavy tasks it remains competitive. In Arabic dependency parsing work, AraBERTv2 reached up to 84.03 percent UAS on the Prague Arabic Dependency Treebank.

## Assessment for SVR

- Strengths: small, fast, well documented, easy to fine tune with a standard classification head, widely used in published Arabic classification work.
- Weaknesses: MSA heavy pretraining is a mismatch for Egyptian dialect voicemail transcripts. The Twitter variant helps with dialect but is still not Egyptian specific.
- Verdict: a solid baseline, not the first choice for Egyptian dialect. Use it as a baseline to beat, and prefer MARBERTv2 or EgyBERT for the main text classifier.

## Source

- Model card: https://huggingface.co/aubmindlab/bert-base-arabertv2
- Paper: Antoun, Baly, and Hajj, AraBERT, 2020.
