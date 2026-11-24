# SVR Recommendations

**Project:** Smart Voicemail Router (SVR)
**Date:** 13 November 2026
**What this file is:** the recommendations from the literature research, kept current. This is the main knowledge source for the AI agent. Read this file first. The full literature research, with 14 picked papers and every source, is in `svr-model-selection-report.md`. The 46 supporting research notes are in `research/notes/`.

**Dataset:** SVR Voicemail Corpus, 6,522 Egyptian Arabic voicemails, 12.6 hours, 16 kHz mono WAV, 6,024 transcripts from Whisper large-v3. Clean training set 5,096 rows: train 3,575, validation 1,003, test 518, stratified, split seed 42. The clean set was reduced from 5,751 rows on 13 November 2026 by excluding the 655 worst transcripts (Whisper logprob below -0.30).

**Task:** multi-task classification, four labels per voicemail: complaint_category (11 classes), complaint_urgency (3 classes), customer_state (5 classes), churn_risk (2 classes, at_risk 0.56 percent, 20 rows in train).

**Data note:** the voicemails are simulated. They were recorded by people for data collection, not by real customers, and the emotions in them are acted. Even a human annotator cannot reliably judge the emotion (mad, calm, and the rest) from the voice alone. For that reason the transcription and the words are the main signal: the category, the urgency, and the customer state are all judged from the words. The audio emotion model is an experiment. It must prove it adds signal over the text alone, and if it does not, it is dropped.

## 1. Recommended text model

**First choice: EgyBERT**

- Hugging Face: https://huggingface.co/faisalq/EgyBERT
- Paper: https://arxiv.org/abs/2408.03524
- What it is: a BERT-base encoder pretrained only on Egyptian dialect, 10.4 GB of Egyptian tweets and forums, vocabulary 75k.
- Why it is first: it is the only encoder pretrained only on Egyptian dialect, and it scored the best published average on 10 Egyptian classification datasets at 84.25 percent F1, just ahead of MARBERTv2 at 83.68 percent. The dialect match with SVR data is exact.
- Caveat: its margin over MARBERTv2 is small (0.57 F1 points) and its evaluation was on tweets and short texts, not transcribed voicemail, so confirm it on SVR validation data. Check the tokenizer on SVR transcripts before training. Two real risks to weigh: EgyBERT is an arXiv preprint, not yet peer reviewed, and it is barely adopted, with 47 downloads on Hugging Face against 21,254 for MARBERTv2. That does not make it wrong, but it means the team must verify the checkpoint loads cleanly and the tokenizer behaves before committing to it.

**Run in parallel: MARBERTv2**

- Hugging Face: https://huggingface.co/UBC-NLP/MARBERTv2
- Paper: https://arxiv.org/abs/2109.01703
- What it is: a BERT-base encoder (163M parameters, vocabulary 100k) pretrained on 1 billion Arabic tweets covering many dialects.
- Why it is the parallel fallback: it is the most proven dialect encoder, the most widely used in shared tasks, and the safest fallback if EgyBERT has a checkpoint or tokenizer problem. It wins or places second in nearly every Arabic dialect benchmark in the papers. Pick the winner by macro F1 on the SVR validation set. Tie-break rule: if EgyBERT and MARBERTv2 are within one standard deviation of each other on validation mean macro-F1, pick MARBERTv2, because it is far more battle tested.

**Other text models on the shortlist**

- AraBERTv2, baseline: https://huggingface.co/aubmindlab/bert-base-arabertv2 (paper: https://arxiv.org/abs/2003.00104). MSA news pretraining, weakest on dialect, useful only as a baseline to show the gain from dialect pretraining.
- CAMeLBERT-mix, third candidate: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix (paper: https://arxiv.org/abs/2103.06678). Pretrained on a mix of MSA, dialect, and classical Arabic. Use if time allows.
- AraRoBERTa-EGY, Egyptian-only RoBERTa, mentioned for completeness: https://huggingface.co/reemalyami/AraRoBERTa-EGY (paper: https://aclanthology.org/2022.wanlp-1.18/). Peer reviewed and Egyptian only, but pretrained on only 37.2 million tokens, far less than EgyBERT at 1.07 billion. The 2026 VarDial study found dialect-specific models beat general models only with substantial pretraining data, so do not recommend it as a first or second choice. Use only as an extra comparison if time allows.
- AraModernBERT, long context candidate: https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0. Context 8,192 tokens. Not needed for SVR: measured transcript lengths on the 6,024 SVR transcripts show a 99th percentile of about 53 tokens and a maximum of about 93 tokens, with zero rows over 128 tokens, so no transcript comes close to 512 tokens. Keep it off the shortlist unless the transcript set changes.
- Do not use as the main classifier: Jais, AceGPT, ALLaM, AraT5. They are decoder or generation models, too large (7B to 70B), and not Egyptian specific. They are useful only as zero shot baselines or teacher models.

## 2. Recommended speech model

**First choice for direct audio classification: wav2vec2 XLS-R 300M**

- Hugging Face: https://huggingface.co/facebook/wav2vec2-xls-r-300m
- Paper: https://arxiv.org/abs/2111.09296
- What it is: a wav2vec2 encoder with about 317M parameters, pretrained on 436k hours of speech in 128 languages, including 95 hours of Arabic. It takes 16 kHz raw waveform input, which matches SVR audio exactly, and it has a native Hugging Face classification class.
- Why it is first: it is the smallest model here with real multilingual and Arabic pretraining, and it is the standard choice for low resource speech fine tuning on a 12.6 hour dataset. Plan: frozen encoder first with pooled hidden states and a small multi task head, then partial fine tuning, unfreezing only the top 2 to 4 transformer layers at a low learning rate (1e-5 to 3e-5).

**Keep Whisper large-v3 for transcription**

- Hugging Face: https://huggingface.co/openai/whisper-large-v3
- Paper: https://arxiv.org/abs/2212.04356
- Whisper large-v3 stays the transcription model. It is the best Arabic ASR model in the comparisons found. Its frozen encoder features are also the strongest for Arabic emotion in the KuralHub benchmark (82.0 percent accuracy on ANAD, against 71 percent for WavLM large and 61 to 63 percent for XLS-R), so test Whisper encoder features as a second audio candidate. Do not fine tune the full 1.55B Whisper model.

**Other speech models**

- WavLM base plus: strong for speaker and prosody information, a candidate for customer_state only. HuBERT (English only) is a control baseline only. The Egyptian XLS-R community checkpoint `IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53` (https://huggingface.co/IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53, 2,146 downloads, updated May 2025) is worth checking as a transcription candidate and as a possible fine-tuning start, but verify its quality first because it is a community checkpoint, not a peer reviewed release. The older `othrif/wav2vec2-large-xlsr-egyptian` checkpoint (187 downloads, March 2021) is superseded by it.

**How the text and speech routes relate:** the text route (transcript classification) is the main route and must be built first. Direct audio classification is a second route that can add signal on tone dependent labels (customer_state, urgency). Compare it against the text pipeline on the same validation split. It does not need to beat text on all four labels to be useful.

## 3. Multi-task setup

- One shared pretrained encoder, four separate classification heads, one head per label (hard parameter sharing, the MT-DNN template). Paper: https://arxiv.org/abs/1901.11504
- Loss weighting: use Kendall uncertainty weighting rather than fixed equal weights. Equal weights let the 9-class category loss dominate while the churn head starves. Uncertainty weighting learns one scalar per task and adapts during training, with no weight grid search. Paper: https://arxiv.org/abs/1705.07115
- Keep the saved per-class weights inside each head's loss (churn at_risk 91.0, mad 6.84), capped so the extreme churn weight does not destabilize training. Cap the maximum weight at 10 to 20, or at the square root of the balanced weight, and test the cap on validation. Compare three variants on validation macro-F1 per task: class weights as saved, capped class weights, and weighted random sampling with no loss weights.
- Do not use GradNorm as the first choice. It adds complexity and a second optimizer loop for a gain that is not needed at this scale. Paper: https://arxiv.org/abs/1711.02257

## 4. Handling severe class imbalance

- Baseline: the saved class weights, with the extreme churn weight capped at 10 to 20. Reported gains from class weights in the literature are macro F1 0.80 to 0.89 on comparable imbalanced text tasks.
- Mandatory second step: per-class threshold tuning on the validation set for the churn head. No training-time method alone can fix a class with about 20 training rows. Threshold tuning sets a usable operating point and is cheap and reliable. Reported gain from per-label threshold optimization is about plus 0.017 absolute macro F1.
- Focal loss: do not use it as the first choice. It was the worst method (macro F1 0.79) when minority classes had only hundreds of rows, and the best (0.90) only once the minority was enlarged. Paper: https://arxiv.org/abs/1708.02002
- Do not use SMOTE on raw text. It does not apply to discrete text and is not usable in an end-to-end fine tuning pipeline. It can only run on frozen embeddings, which is not our pipeline.
- Next method to test: targeted augmentation of the churn rows (LLM paraphrases with human review, aiming for 100 to 200 reviewed variants). This is the only method that adds genuinely new information.
- Oversampling the minority classes by duplication is allowed as a trial, but it repeats the same rows and risks overfitting. Undersampling the majority classes throws away real data and is not recommended.

## 5. Recommended hyperparameters

For fine-tuning a BERT-style encoder on the SVR training set (3,575 rows). Values come from the BERT paper, the RoBERTa paper, Mosbach et al. 2021 on fine-tuning stability, and the Hugging Face Trainer guide.

| Hyperparameter | Recommended value | Source |
|---|---|---|
| Learning rate | 2e-5 (sweep 1e-5, 2e-5, 3e-5) | BERT paper (2e-5 to 5e-5); RoBERTa (1e-5 to 3e-5); Mosbach (small LR) |
| Batch size | 16 effective (8 per device plus 2 gradient accumulation steps if memory is tight) | BERT and RoBERTa papers (16 or 32) |
| Epochs | 3, with max 5 and early stopping | BERT (2 to 4); RoBERTa (10 with early stopping); Mosbach (train longer, small LR) |
| Warmup ratio | 0.1 (0.06 per RoBERTa also acceptable) | BERT (first 10 percent of steps); RoBERTa (first 6 percent) |
| Weight decay | 0.01 (must set explicitly; Hugging Face Trainer defaults to 0.0) | BERT and RoBERTa papers |
| Max sequence length | 128 (raise to 256 only if the 99th percentile token length exceeds 128) | BERT GLUE setup; Arabic dialect studies used 128 |
| Optimizer | AdamW, beta1 0.9, beta2 0.999, epsilon 1e-8, bias correction ON | BERT and RoBERTa papers; Mosbach (bias correction is part of the stability fix) |
| Scheduler | Linear warmup then linear decay to 0 | BERT and RoBERTa papers; Hugging Face Trainer default |
| Gradient accumulation | 2 steps only if per-device batch must drop to 8 | Hugging Face course example (4 x 4 = 16 effective) |
| Early stopping | Patience 2 epochs on validation mean macro-F1, load best checkpoint | RoBERTa (early stopping on dev metric) |
| Dropout / grad clip | 0.1 / max norm 1.0 | BERT paper (dropout always 0.1); Hugging Face Trainer default |
| Mixed precision | fp16 or bf16 ON for GPU training | Standard for BERT fine-tuning, halves memory and speeds up training; use bf16 if the GPU supports it, otherwise fp16 |
| Seeds | 5 seeds (42, 1337, 2023, 7, 99), report mean plus std | RoBERTa (median of 5); Mosbach (never trust one run) |
| Small and imbalanced data rules | Lower LR (2e-5, not 5e-5), fewer fixed epochs with early stopping, class weights in the loss (already saved), threshold tuning for churn on validation | BERT paper (small sets are more sensitive); Mosbach; class weight literature |

Sources: BERT paper https://arxiv.org/abs/1810.04805 ; RoBERTa paper https://arxiv.org/abs/1907.11692 ; Mosbach et al. 2021 https://arxiv.org/abs/2006.03609 ; Hugging Face Trainer guide https://huggingface.co/docs/transformers/en/main_classes/trainer

## 6. Training phases in order

0. Preparation and frozen checks: splits, label distribution, token lengths, class weights. Freeze the splits now: no re-splitting after results exist. Check for data leakage between train and test (no shared text groups, no duplicate transcripts across splits) before any training starts.
1. Baseline: TF-IDF plus logistic regression per field, class_weight balanced. Baseline validation macro-F1 to beat: category 0.7261, urgency 0.6789, state 0.5561, churn 0.8840, mean 0.7113.
2. Single-task fine-tuning: MARBERTv2 per field, 5 seeds, the reference the multi-task model must match.
3. Multi-task fine-tuning: shared encoder, four heads, uncertainty weighted task losses plus per-task class weights, early stopping on mean validation macro-F1.
4. Validation, churn threshold tuning, and model selection, on validation only.
5. Final test evaluation, once, on the frozen 518 row test set.
6. Error analysis (50 errors per field grouped by cause) and deployment readiness (calibration, latency).
7. Retrain on audited labels: after the team audit finishes and the corrected labels are applied to the dataset, rerun the training notebook on the cleaned dataset. No architecture or hyperparameter changes are needed for this step, only the data changes. This is the final model.

Model selection: EgyBERT first, then MARBERTv2 as the parallel comparison, CAMeLBERT-mix and AraBERTv2 as further comparisons, XLM-RoBERTa as an optional multilingual control. Compare encoders at fixed hyperparameters, pick on validation mean macro-F1. Never tune on test.

## 7. Metrics to report

Primary metric per field: macro-F1, with macro-precision and macro-recall. Also per-class precision, recall, F1 with support counts, confusion matrix (counts), and accuracy for context only. Micro-F1 must not be reported as a separate insight, because on single-label data it equals accuracy. Combined score, if needed: unweighted mean of the four macro-F1 values, always shown with all four values visible, plus each task compared against its single-task reference.

For churn (at_risk 0.56 percent): at_risk precision, recall, F1 with raw counts, average precision (precision-recall AUC, chance level 0.0056), balanced accuracy, and the validation-tuned decision threshold. Test-only churn recall is meaningless with 1 at-risk row in test, so report churn on validation plus test pooled (8 at-risk rows, always with counts, for example "recall 6 of 8"), and prefer 5-fold stratified cross-validation for the churn estimate.

## 8. Practical constraints the team must plan for

- Compute: there is no GPU on the project VM, so training runs on the team machines. A GPU is strongly recommended. Phase 2 is the largest block: 3 encoders times 4 tasks times 5 seeds is 60 runs, each about 223 steps per epoch at batch 16, and each run takes minutes on one GPU, so Phase 2 is roughly 3 to 5 hours on a single GPU. On CPU only, each run takes roughly 30 to 60 minutes, which turns Phase 2 into 30 to 45 hours. Plan the GPU time before starting Phase 2.
- Labels are unaudited: the training labels may contain mistakes, and the team audit runs in parallel with training for about a month. Train normally on the current labels, and do not wait for the audit. When the audit finishes and the corrections are applied, Phase 7 retrains on the cleaned dataset. A low result before the audit does not mean the model or the hyperparameters are wrong.
- Small dataset: 3,575 training rows is small for fine-tuning. That is why the learning rate is low (2e-5, not 5e-5), epochs are capped at 5 with early stopping, and 5 seeds are required. Never trust a single run.
- Severe imbalance: churn at_risk is 0.56 percent (20 training rows). No training-time method alone fixes that. Class weights plus validation threshold tuning are mandatory, and churn must be reported on validation plus test pooled with raw counts, never on test alone.

## Sources

Full literature research with 14 picked papers, every source, and claims without a direct source: `svr-model-selection-report.md` in this folder. Supporting notes: `research/notes/` (46 notes on models, methods, training, and papers).
