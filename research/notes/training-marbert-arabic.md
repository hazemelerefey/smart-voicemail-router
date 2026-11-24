---
title: "MARBERT and Arabic BERT models for Egyptian dialect text"
tags: [training, model-selection, arabic, marbert, dialect, svr]
source_url: "https://aclanthology.org/2021.acl-long.551/"
---

# MARBERT and Arabic BERT models for Egyptian dialect text

Source: Abdul-Mageed, Elmadany, Nagoudi, "ARBERT and MARBERT: Deep Bidirectional Transformers for Arabic", Proceedings of ACL-IJCNLP 2021, pages 7088 to 7105 (https://aclanthology.org/2021.acl-long.551/). Model card facts verified against the UBC-NLP/MARBERT Hugging Face page.

## MARBERT facts

- MARBERT is a BERT-base architecture model (12 layers, 768 hidden size, 12 heads, about 163M parameters) pre-trained on 1 billion Arabic tweets, 128GB of text, 15.6B tokens.
- It was trained with the masked language modeling objective only, no next sentence prediction, because tweets are short.
- It covers both Dialectal Arabic and Modern Standard Arabic. Tweets were included if they contained at least 3 Arabic words.
- MARBERTv2 is the updated version and the one to use (UBC-NLP/MARBERTv2 on Hugging Face).

## Why MARBERT fits SVR

SVR transcripts are Egyptian Arabic customer voicemails transcribed by Whisper: informal, spoken, dialectal language, not formal Modern Standard Arabic. MARBERT is pre-trained on exactly that register (dialectal social media Arabic). Domain-specific pre-trained models almost always beat general multilingual models on their domain, and MARBERT is the standard dialectal Arabic encoder.

Supporting evidence: a 2026 AraSentEval paper (University of Tripoli team, OSACT7) fine-tuned MARBERTv2 and CAMeLBERT for multi-dialect sentiment analysis including Egyptian, and MARBERTv2 was their best system with macro-F1 84.29 percent on the official test set. A separate Egyptian Arabic hate speech model on Hugging Face (IbrahimAmin/marbertv2-finetuned-egyptian-hate-speech-classification) is a fine-tuned MARBERTv2 for Egyptian dialect classification, showing the same base model works for Egyptian classification tasks. A 2026 dialect bias study fine-tuned AraBERT, MARBERT, CAMeLBERT-DA, and XLM-RoBERTa under identical settings (max sequence length 128, batch size 16, learning rate 2e-5) and MARBERT reached macro-F1 0.871 on its task, the highest of the four.

## Alternatives and their place

| Model | Hugging Face id | When to use it |
|---|---|---|
| MARBERTv2 | UBC-NLP/MARBERTv2 | First choice for SVR. Dialectal Arabic, tweet register, strongest published results on dialect tasks. |
| CAMeLBERT-DA | CAMeL-Lab/bert-base-arabic-camelbert-da | Second candidate. Pre-trained on dialectal Arabic. Include in the model comparison. |
| AraBERTv2 | aubmindlab/bert-base-arabertv02 | MSA focused (135M parameters). Include as a control to show whether dialect pre-training matters. |
| XLM-RoBERTa base | xlm-roberta-base | Multilingual baseline (278M parameters). Include as a control; expect it below MARBERT on dialectal text. |
| mBERT | bert-base-multilingual-cased | Weakest expected option. Only include if compute for the others is unavailable. |

## Fine-tuning settings used for Arabic models in the literature

The dialect bias study above used max sequence length 128, batch size 16, learning rate 2e-5 with the Hugging Face Trainer. Cross-dialectal NER work used batch size 8 to 12 and learning rate 2e-5 for the pre-trained parameters. Both agree with the BERT and RoBERTa paper values, so no special Arabic-only hyperparameters are needed. Use the same recommended recipe as for BERT, with MARBERTv2 as the encoder.

## Assessment for SVR

Start with MARBERTv2. Run the baseline and the fine-tune comparison across at most three encoders (MARBERTv2, CAMeLBERT-DA, AraBERTv2) so the comparison stays cheap, with XLM-RoBERTa as an optional fourth. Keep hyperparameters fixed across encoders during the comparison (learning rate 2e-5, batch size 16, 3 epochs, warmup 0.1, weight decay 0.01, max length 128) so differences reflect the encoder, not the tuning. Pick the winner on validation mean macro-F1 across the four tasks, then tune hyperparameters only for the winner.
