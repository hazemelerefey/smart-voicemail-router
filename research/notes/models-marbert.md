---
title: "MARBERTv2 - Dialectal Arabic BERT"
tags: [svr, models, arabic-nlp, text-classification, marbert, dialect]
source_url: "https://huggingface.co/UBC-NLP/MARBERTv2"
---

# MARBERTv2

## What it is

MARBERT is a BERT based model for dialectal Arabic, from the University of British Columbia NLP group, Abdul-Mageed et al. 2021. MARBERTv2, Elmadany et al. 2023, is an enhanced version pretrained on a larger corpus for longer. It is an encoder only model built for classification of social media and spoken style Arabic text.

## Hugging Face

- Model ID: `UBC-NLP/MARBERTv2`
- Link: https://huggingface.co/UBC-NLP/MARBERTv2
- First version: `UBC-NLP/MARBERT`
- Link: https://huggingface.co/UBC-NLP/MARBERT

## Size

- About 163M parameters.
- Architecture: BERT base, 12 layers, 768 hidden size, 12 attention heads.
- Vocabulary: 100,000 WordPiece tokens.

## Training data

- Pretrained on 1 billion Arabic tweets, about 128 GB of text, randomly selected from a pool of 6 billion tweets.
- The tweets cover both MSA and dialectal Arabic, including Egyptian, Levantine, Gulf, and Maghrebi varieties. This is the key difference from AraBERT: the training distribution is spoken and social Arabic, not news MSA.
- MARBERTv2 was pretrained on a larger corpus and for longer than MARBERTv1, with the same tweet based approach.

## Classification performance

- MARBERT achieved state of the art results on most dialectal Arabic tasks at release, outperforming AraBERT and multilingual models on the ARLUE benchmark, especially on tasks whose data are mainly dialectal.
- DialectSentEval 2026 Subtask 1, three class sentiment classification across Moroccan, Egyptian, Jordanian, and Saudi Arabic: MARBERTv2 was the strongest single model at 94.07 percent macro F1, ahead of CAMeLBERT at 81.96 percent and AraBERTv2 at 79.77 percent. Note this is a small hotel review dataset, so treat the gap as direction, not as a guarantee on SVR data.
- MuDRiC multi dialect commonsense validation, binary classification: MARBERTv2 averaged 78.16 percent accuracy, with 80.73 percent on Egyptian, the best of the three encoders tested, ahead of CAMeLBERT-mix at 72.34 percent and AraBERTv2 at 65.34 percent.
- In a 2024 multi dialect intent detection task, ArBanking77, a MARBERTv2 based system reached 0.9470 F1 on the Palestinian dialect validation set.
- MARBERTv2 is still the default encoder in 2025 and 2026 Arabic shared task systems for stance, sentiment, and genre classification, often with class weighting to handle imbalance, which matches the SVR situation.

## Egyptian dialect coverage

- Yes, directly. Egyptian Arabic is one of the largest dialect groups in the tweet corpus. No Egyptian only model, but Egyptian is well represented, and the MuDRiC Egyptian score above is evidence for it.

## Assessment for SVR

- Strengths: best documented dialect coverage of the general Arabic encoders, strong and repeated results on dialect classification, same size class as AraBERT so training cost is similar, standard BERT classification head works for multi task learning with four heads.
- Weaknesses: tweet style is short and noisy, while voicemail transcripts are longer spoken complaints. It is not Egyptian only, so an Egyptian only model may beat it by a small margin.
- Verdict: the strongest safe first choice if the team wants a proven general dialect encoder. It is the main rival to EgyBERT for the top recommendation. Run both and pick on the SVR validation set using macro F1, not accuracy, because of the severe class imbalance.

## Source

- Model card: https://huggingface.co/UBC-NLP/MARBERTv2
- Paper: Abdul-Mageed, Elmadany, and Nagoudi, ARBERT and MARBERT, ACL-IJCNLP 2021.
- Comparison: DialectSentEval 2026, https://aclanthology.org/2026.arabicnlp-sharedtasks.181.pdf
