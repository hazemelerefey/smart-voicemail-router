---
title: "Text Model Comparison for SVR - Recommendation"
tags: [svr, models, recommendation, text-classification, egyptian-dialect]
source_url: "https://arxiv.org/abs/2408.03524"
---

# Text Model Comparison for SVR: Recommendation

## The SVR text task

SVR classifies Whisper transcripts of Egyptian Arabic voicemails into four labels at once: complaint_category with 9 classes, complaint_urgency with 3, customer_state with 5, and churn_risk with 2. The clean training set is 5,751 rows, with train 4,031, validation 1,136, and test 584. Churn at risk is only 0.5 percent. The model must be a multi task encoder with four classification heads, trained with class weighting, and judged by macro F1, not accuracy.

## Comparison table

| Model | Size | Dialect focus | Egyptian evidence |
| EgyBERT | BERT base, vocab 75k | Egyptian only | Best average on 10 Egyptian datasets, F1 84.25 percent, accuracy 87.33 percent |
| MARBERTv2 | 163M, vocab 100k | Multi dialect tweets | Second on Egyptian tasks, F1 83.68 percent, best on MuDRiC and DialectSentEval 2026 |
| CAMeLBERT-mix | About 110M, vocab 30k | MSA plus dialect plus classical | 81.96 percent macro F1 on DialectSentEval 2026, behind MARBERTv2 |
| AraBERTv2 | About 136M, vocab 60k | MSA news | 79.77 percent macro F1 on DialectSentEval 2026, weakest on dialect |
| AraModernBERT | About 149M, vocab 50k, context 8192 | MSA focus | No Egyptian classification result found, long context is its advantage |
| AraT5v2 | 220M, encoder decoder | MSA plus dialect | Strong for generation, awkward for four label classification |
| Jais 13B | 13B, decoder only | General Arabic | Strong on knowledge benchmarks, too large for classification |
| AceGPT 7B and 13B | 7B and 13B, decoder only | General Arabic | Strong on instruction benchmarks, too large for classification |
| ALLaM 7B to 70B | 7B to 70B, decoder only | General Arabic | State of the art on Arabic MMLU, too large for classification |

## Top recommendation

Use EgyBERT as the first text classifier, at https://huggingface.co/faisalq/EgyBERT

Reasoning: it is the only encoder pretrained only on Egyptian dialect, it has the best published average on Egyptian classification tasks, and its size matches the training budget for a 4,031 row training set. The margin over MARBERTv2 is small, so the team must confirm it on SVR validation data, but the dialect match is exact and the published evidence points the same way.

## Fallback and comparison plan

1. First choice: EgyBERT, `faisalq/EgyBERT`.
2. Second choice, run in parallel: MARBERTv2, `UBC-NLP/MARBERTv2`, at https://huggingface.co/UBC-NLP/MARBERTv2 . It is the most proven dialect encoder, the most widely used in shared tasks, and the safest fallback if EgyBERT has a checkpoint or tokenizer problem.
3. Third candidate if time allows: AraModernBERT, `NAMAA-Space/AraModernBert-Base-V1.0`, for long transcripts that exceed 512 tokens.
4. Baseline: AraBERTv2, to show the gain from dialect pretraining.
5. Do not use Jais, AceGPT, ALLaM, or AraT5 as the main classifier. They are decoder or generation models, too large, and not Egyptian specific. They are useful only as zero shot baselines or teacher models.

## Training notes for the team

- Use the same splits, same multi task heads, and same class weighting for every encoder, so the comparison is fair.
- Report macro F1 per label, and report churn at risk on validation plus test pooled, because the test set holds only 1 at risk row.
- Watch truncation: BERT models cut at 512 tokens. Check how many SVR transcripts exceed that, and if it is a real problem, AraModernBERT with 8,192 tokens becomes more valuable.
- Check the EgyBERT tokenizer on SVR transcripts before training, because it was trained on tweets and forums, not on transcribed speech.

## Sources

- EgyBERT paper: https://arxiv.org/abs/2408.03524
- MARBERTv2 model: https://huggingface.co/UBC-NLP/MARBERTv2
- DialectSentEval 2026: https://aclanthology.org/2026.arabicnlp-sharedtasks.181.pdf
- MuDRiC paper: https://arxiv.org/pdf/2508.13130
