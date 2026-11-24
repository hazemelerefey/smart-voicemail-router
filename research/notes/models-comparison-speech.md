---
title: "Speech Model Comparison for SVR - Recommendation"
tags: [svr, models, recommendation, speech, classification]
source_url: "https://huggingface.co/facebook/wav2vec2-xls-r-300m"
---

# Speech Model Comparison for SVR: Recommendation

## The SVR speech task

SVR audio is 16 kHz mono WAV, 12.6 hours total, 6,522 voicemails. The current pipeline transcribes with Whisper large-v3 and classifies the text. Direct audio classification is a second route: classify the audio itself, which can capture tone, urgency, and emotion that the transcript loses. That is relevant to customer_state and complaint_urgency in particular. The dataset is small for speech fine tuning, so the model must work with frozen features first, then partial fine tuning.

## Comparison table

| Model | Size | Arabic coverage | Best use for SVR |
| XLS-R 300M | About 317M | Multilingual, 128 languages, 95h Arabic | Fine tune for classification, first choice |
| Whisper large-v3 encoder | 1,550M total, encoder about half | 739h Arabic, 99 languages | Frozen features, already in pipeline for ASR |
| WavLM base plus | About 95M | English dominated | Speaker and emotion features, second candidate for customer_state |
| WavLM large | About 317M | English dominated | Frozen emotion features, heavier than base plus |
| HuBERT base | About 95M | English only | Control baseline only |
| HuBERT large | About 317M | English only | Control baseline only |
| mHuBERT base 147 | About 94M | Multilingual, 147 languages | Frozen Arabic features, third candidate |
| MMS 1B | About 1,000M | Over 1,000 languages | Too large, frozen features only if tested |
| Egyptian XLSR-53 | Large XLSR class | Egyptian ASR fine tune | Better transcription candidate, or fine tune base for classification |

## Top recommendation

Use wav2vec2 XLS-R 300M as the first speech encoder to fine tune for direct audio classification, at https://huggingface.co/facebook/wav2vec2-xls-r-300m

Reasoning: it is the smallest model in this set that has real multilingual and Arabic pretraining, it takes 16 kHz raw waveform input which matches SVR audio exactly, it has a native Hugging Face classification class, and it is the standard model for low resource speech fine tuning. The 300M size is trainable on a 12.6 hour dataset with frozen first, then partial fine tuning, while the 1B and 2B versions and Whisper large are too large to fine tune fully on this data.

## What Whisper is for

Keep Whisper large-v3 for transcription. That is its proven role in SVR, and it is the best Arabic ASR model in the comparisons found here. Its frozen encoder features are also the strongest for Arabic emotion in the KuralHub benchmark, at 82.0 percent test accuracy on ANAD, against 71 percent for WavLM large and 61 to 63 percent for XLS-R. That result is with a frozen backbone and a two layer head, so it is a fair comparison of representation quality. The team should test Whisper encoder features as a second candidate, but not fine tune the full 1.55B model.

## Training plan for the team

1. First: XLS-R 300M, frozen encoder, pooled hidden states, small multi task head, one head per label. This is the low risk baseline for direct audio classification.
2. Second: XLS-R 300M, partial fine tuning, unfreeze the top 2 to 4 transformer layers only, with a low learning rate around 1e-5 to 3e-5, and early stopping on validation macro F1.
3. Third: Whisper large-v3 encoder, frozen, pooled features, same small head, to test whether Whisper features beat XLS-R features on customer_state and urgency.
4. Fourth, optional: WavLM base plus, partial fine tuning, for customer_state only, because its strength is speaker and prosody information.
5. Do not fine tune HuBERT English checkpoints as the main model. Use them only as a control to show that Arabic aware pretraining matters.
6. Compare direct audio classification against the current text pipeline on the same validation split. Audio classification does not need to beat text classification on all four labels to be useful. It only needs to add signal on tone dependent labels such as customer_state and urgency.
7. Check the Egyptian XLS-R checkpoint, `IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53`, as a transcription candidate and as a possible fine tuning start, but verify its quality first, because it is a community checkpoint, not a peer reviewed release.

## Sources

- XLS-R model: https://huggingface.co/facebook/wav2vec2-xls-r-300m
- Whisper model: https://huggingface.co/openai/whisper-large-v3
- Arabic emotion benchmark: https://aaivu.github.io/KuralHub/languages/arabic.html
- Whisper Arabic benchmark: https://ar5iv.labs.arxiv.org/html/2306.02902
- Egyptian XLSR: https://huggingface.co/IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53
