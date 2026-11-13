# SVR Model Selection Report

**Project:** Smart Voicemail Router (SVR)
**Date:** 12 November 2026
**Dataset:** SVR Voicemail Corpus, 6,522 Egyptian Arabic voicemails, 12.6 hours, 16 kHz mono WAV, 6,024 transcripts from Whisper large-v3. Clean training set 5,751 rows: train 4,031, validation 1,136, test 584, stratified.
**Task:** Multi-task classification, four labels per voicemail: complaint_category (9 classes), complaint_urgency (3 classes), customer_state (5 classes), churn_risk (2 classes, at_risk 0.5 percent).
**Sources:** 46 research notes in the vault at `research/notes/`, covering models, methods, training, and papers. Every factual claim below traces to a vault note or a fetched source.

Note: this report was written on 12 November 2026 when the clean set was 5,751 rows (train 4,031, validation 1,136, test 584). The clean set was later reduced to 5,096 rows (train 3,575, validation 1,003, test 518) by excluding the 655 worst transcripts (Whisper logprob below -0.30). The numbers in this report refer to the 5,751 row set. The current numbers and the current recommendations are in `recommendations.md` in this folder.

---

## Part 1: Recommended Models and Hyperparameters

### 1.1 Recommended text model

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
- Why it is the parallel fallback: it is the most proven dialect encoder, the most widely used in shared tasks, and the safest fallback if EgyBERT has a checkpoint or tokenizer problem. It wins or places second in nearly every Arabic dialect benchmark in the papers below. Pick the winner by macro F1 on the SVR validation set. Tie-break rule: if EgyBERT and MARBERTv2 are within one standard deviation of each other on validation mean macro-F1, pick MARBERTv2, because it is far more battle tested.

**Other text models on the shortlist**

- AraBERTv2, baseline: https://huggingface.co/aubmindlab/bert-base-arabertv2 (paper: https://arxiv.org/abs/2003.00104). MSA news pretraining, weakest on dialect, useful only as a baseline to show the gain from dialect pretraining.
- CAMeLBERT-mix, third candidate: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix (paper: https://arxiv.org/abs/2103.06678). Pretrained on a mix of MSA, dialect, and classical Arabic. Use if time allows.
- AraRoBERTa-EGY, Egyptian-only RoBERTa, mentioned for completeness: https://huggingface.co/reemalyami/AraRoBERTa-EGY (paper: https://aclanthology.org/2022.wanlp-1.18/). Peer reviewed and Egyptian only, but pretrained on only 37.2 million tokens, far less than EgyBERT at 1.07 billion. The 2026 VarDial study found dialect-specific models beat general models only with substantial pretraining data, so do not recommend it as a first or second choice. Use only as an extra comparison if time allows.
- AraModernBERT, long context candidate: https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0 . Context 8,192 tokens. Not needed for SVR: measured transcript lengths on the 6,024 SVR transcripts show a 99th percentile of about 53 tokens and a maximum of about 93 tokens, with zero rows over 128 tokens, so no transcript comes close to 512 tokens. Keep it off the shortlist unless the transcript set changes.
- Do not use as the main classifier: Jais, AceGPT, ALLaM, AraT5. They are decoder or generation models, too large (7B to 70B), and not Egyptian specific. They are useful only as zero shot baselines or teacher models.

### 1.2 Recommended speech model

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

### 1.3 Multi-task setup

- One shared pretrained encoder, four separate classification heads, one head per label (hard parameter sharing, the MT-DNN template). Paper: https://arxiv.org/abs/1901.11504
- Loss weighting: use Kendall uncertainty weighting rather than fixed equal weights. Equal weights let the 9-class category loss dominate while the churn head starves. Uncertainty weighting learns one scalar per task and adapts during training, with no weight grid search. Paper: https://arxiv.org/abs/1705.07115
- Keep the saved per-class weights inside each head's loss (churn at_risk 89.859, mad 7.234), capped so the extreme churn weight does not destabilize training. Cap the maximum weight at 10 to 20, or at the square root of the balanced weight, and test the cap on validation. Compare three variants on validation macro-F1 per task: class weights as saved, capped class weights, and weighted random sampling with no loss weights.
- Do not use GradNorm as the first choice. It adds complexity and a second optimizer loop for a gain that is not needed at this scale. Paper: https://arxiv.org/abs/1711.02257

### 1.4 Handling severe class imbalance

- Baseline: the saved class weights, with the extreme churn weight capped at 10 to 20. Reported gains from class weights in the literature are macro F1 0.80 to 0.89 on comparable imbalanced text tasks.
- Mandatory second step: per-class threshold tuning on the validation set for the churn head. No training-time method alone can fix a class with about 22 training rows. Threshold tuning sets a usable operating point and is cheap and reliable. Reported gain from per-label threshold optimization is about plus 0.017 absolute macro F1.
- Focal loss: do not use it as the first choice. It was the worst method (macro F1 0.79) when minority classes had only hundreds of rows, and the best (0.90) only once the minority was enlarged. Paper: https://arxiv.org/abs/1708.02002
- Do not use SMOTE on raw text. It does not apply to discrete text and is not usable in an end-to-end fine tuning pipeline. It can only run on frozen embeddings, which is not our pipeline.
- Next method to test: targeted augmentation of the churn rows (LLM paraphrases with human review, aiming for 100 to 200 reviewed variants). This is the only method that adds genuinely new information.
- Oversampling the minority classes by duplication is allowed as a trial, but it repeats the same rows and risks overfitting. Undersampling the majority classes throws away real data and is not recommended.

### 1.5 Recommended hyperparameters

For fine-tuning a BERT-style encoder on the SVR training set (4,031 rows). Values come from the BERT paper, the RoBERTa paper, Mosbach et al. 2021 on fine-tuning stability, and the Hugging Face Trainer guide.

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

### 1.6 Training phases in order

0. Preparation and frozen checks: splits, label distribution, token lengths, class weights. Freeze the splits now: no re-splitting after results exist. Check for data leakage between train and test (no shared text groups, no duplicate transcripts across splits) before any training starts.
1. Baseline: TF-IDF plus logistic regression per field, class_weight balanced.
2. Single-task fine-tuning: MARBERTv2 per field, 5 seeds, the reference the multi-task model must match.
3. Multi-task fine-tuning: shared encoder, four heads, uncertainty weighted task losses plus per-task class weights, early stopping on mean validation macro-F1.
4. Validation, churn threshold tuning, and model selection, on validation only.
5. Final test evaluation, once, on the frozen 584 row test set.
6. Error analysis (50 errors per field grouped by cause) and deployment readiness (calibration, latency).
7. Retrain on audited labels: after the team audit finishes and the corrected labels are applied to the dataset, rerun the training notebook on the cleaned dataset. No architecture or hyperparameter changes are needed for this step, only the data changes. This is the final model.

Model selection: EgyBERT first, then MARBERTv2 as the parallel comparison, CAMeLBERT-mix and AraBERTv2 as further comparisons, XLM-RoBERTa as an optional multilingual control. Compare encoders at fixed hyperparameters, pick on validation mean macro-F1. Never tune on test.

### 1.7 Metrics to report

Primary metric per field: macro-F1, with macro-precision and macro-recall. Also per-class precision, recall, F1 with support counts, confusion matrix (counts), and accuracy for context only. Micro-F1 must not be reported as a separate insight, because on single-label data it equals accuracy. Combined score, if needed: unweighted mean of the four macro-F1 values, always shown with all four values visible, plus each task compared against its single-task reference.

For churn (at_risk 0.5 percent): at_risk precision, recall, F1 with raw counts, average precision (precision-recall AUC, chance level 0.005), balanced accuracy, and the validation-tuned decision threshold. Test-only churn recall is meaningless with 1 at-risk row in test, so report churn on validation plus test pooled (about 7 at-risk rows, always with counts, for example "recall 5 of 7"), and prefer 5-fold stratified cross-validation for the churn estimate.

---

### 1.8 Practical constraints the team must plan for

- Compute: there is no GPU on the project VM, so training runs on the team machines. A GPU is strongly recommended. Phase 2 is the largest block: 3 encoders times 4 tasks times 5 seeds is 60 runs, each about 252 steps per epoch at batch 16, and each run takes minutes on one GPU, so Phase 2 is roughly 3 to 5 hours on a single GPU. On CPU only, each run takes roughly 30 to 60 minutes, which turns Phase 2 into 30 to 45 hours. Plan the GPU time before starting Phase 2.
- Labels are unaudited: the training labels may contain mistakes, and the team audit runs in parallel with training for about a month. Train normally on the current labels, and do not wait for the audit. When the audit finishes and the corrections are applied, Phase 7 retrains on the cleaned dataset. A low result before the audit does not mean the model or the hyperparameters are wrong.
- Small dataset: 4,031 training rows is small for fine-tuning. That is why the learning rate is low (2e-5, not 5e-5), epochs are capped at 5 with early stopping, and 5 seeds are required. Never trust a single run.
- Severe imbalance: churn at_risk is 0.5 percent (about 22 training rows). No training-time method alone fixes that. Class weights plus validation threshold tuning are mandatory, and churn must be reported on validation plus test pooled with raw counts, never on test alone.
- **Data note:** the voicemails are simulated. They were recorded by people for data collection, not by real customers, and the emotions in them are acted. Even a human annotator cannot reliably judge the emotion (mad, calm, and the rest) from the voice alone. For that reason the transcription and the words are the main signal: the category, the urgency, and the customer state are all judged from the words. The audio emotion model is an experiment. It must prove it adds signal over the text alone, and if it does not, it is dropped.

## Part 2: Picked Papers

Each paper below has an official direct hyperlink (DOI, arXiv, ACL Anthology, or publisher link), verified to resolve. The papers are ordered by relevance to SVR, not by date.

### 1. EgyBERT: A Large Language Model Pretrained on Egyptian Dialect Corpora

- Authors: Faisal Qarah
- Year: 2024
- Venue: arXiv preprint arXiv:2408.03524
- Link: https://arxiv.org/abs/2408.03524
- Why it matters: the only encoder pretrained only on Egyptian dialect, and it beat MARBERTv2 across ten Egyptian tasks with 84.25 percent average F1, so it belongs on our model shortlist next to MARBERTv2.

### 2. Arabic Dialect Classification using RNNs, Transformers, and Large Language Models: A Comparative Analysis

- Authors: Omar A. Essameldin, Ali O. Elbeih, Wael H. Gomaa, Wael F. Elsersy
- Year: 2025
- Venue: arXiv preprint arXiv:2506.19753
- Link: https://arxiv.org/abs/2506.19753
- Why it matters: MARBERTv2 is the best dialectal Arabic encoder at 65 percent accuracy and 64 percent F1 on 18 dialects, which supports starting our model from MARBERTv2.

### 3. MTBERT-Attention: An Explainable BERT Model based on Multi-Task Learning for Cognitive Text Classification

- Authors: Hanane Sebbaq and Nour-eddine El Faddouli
- Year: 2023
- Venue: Scientific African, volume 21, article e01799
- Link: https://doi.org/10.1016/j.sciaf.2023.e01799
- Why it matters: a shared BERT encoder with multi-task heads and co-attention reached 97.71 percent accuracy and produced attention-based explanations that beat LIME on fidelity and cost, giving us a precedent for our multi-task design and for attention highlights as ticket explanations.

### 4. Cross-transfer Knowledge between Speech and Text Encoders to Evaluate Customer Satisfaction

- Authors: Luis Felipe Parra-Gallego, Tilak Purohit, Bogdan Vlasenko, Juan Rafael Orozco-Arroyave
- Year: 2024
- Venue: INTERSPEECH 2024
- Link: https://publications.idiap.ch/downloads/papers/2024/Parra-Gallego_INTERSPEECH_2024.pdf
- Why it matters: distilling BERT knowledge into Whisper and wav2vec2 encoders classified satisfaction from call center voicemails at over 92 percent accuracy without ASR at inference, validating our voicemail-to-satisfaction pipeline and flagging transcript error as our main noise source.

### 5. Categorization of Telecom Customers Complaints in Saudi Dialect Using Deep Learning Approach

- Authors: Ibrahim F. Moawad, Mohamed Gammar, Baraa Khaled, Yousef Atif Hazzaa, Yasser Aljohani, and Mohammed Khalid Al-Hamdan
- Year: 2025
- Venue: Proceedings of the 7th Novel Intelligent and Leading Emerging Sciences Conference (NILES), Giza, Egypt
- Link: https://doi.org/10.1109/NILES68063.2025.11232278
- Why it matters: multi-class complaint categorization reached 87.64 percent accuracy, confirming our 9-class complaint_category head will be the hardest label and must be judged on macro F1.
- Note: the 87.64 percent figure comes from a secondary source (a literature review table), not from the paper text itself, so treat it as indicative rather than verified.

### 6. Using the AraBERT Model for Customer Satisfaction Classification of Telecom Sectors in Saudi Arabia

- Authors: Sulaiman Aftan and Habib Shah
- Year: 2023
- Venue: Brain Sciences, volume 13, issue 1, article 147
- Link: https://pmc.ncbi.nlm.nih.gov/articles/PMC9856834/
- Why it matters: AraBERT reached 94.33 percent accuracy on binary satisfaction, beating RNN and CNN, which sets a baseline expectation that a fine-tuned encoder beats classical models on customer text.

### 7. Fine-Tuning MARBERT for Sentiment Analysis in Jordanian Arabic Dialects Using a Synthetic Dialectal Corpus

- Authors: Hashem AL Drous, Hashem Barakat, and Anas Bani Atta
- Year: 2025
- Venue: Journal of Computer Science and Technology Studies, volume 7, number 11, pages 373-386
- Link: https://doi.org/10.32996/jcsts.2025.7.11.36
- Why it matters: MARBERT fine-tuned on only 900 dialectal samples reached 0.88 F1, suggesting our 4,031 training rows are enough, and light preprocessing beats aggressive stripping.

### 8. Sentiment Analysis on Arabic Dialects: A Multi-Dialect Benchmark

- Authors: Abdusalam F. Ahmad Nwesri, Nabila Almabrouk S. Shinbir, and Amani Bahlul Sharif
- Year: 2025
- Venue: Proceedings of the Shared Task on Sentiment Analysis for Arabic Dialects (AHaSIS) at RANLP 2025, pages 86-91
- Link: https://aclanthology.org/2025.ranlp-ahasis.13/
- Why it matters: MARBERTv2 won the six-model benchmark at 79 percent test F1, and a larger AraBERT that led on validation dropped on test, warning us to select models on validation only and never tune on test.

### 9. Enhancing Arabic Sentiment Analysis via MARBERT: Domain Adaptation With Pseudo-Labeling and Contrastive Learning

- Authors: Mohamed R. Ezzeldin, Gaber Sallam Salem Abdalla, and Abdoulie Faal
- Year: 2025
- Venue: Engineering Reports (Wiley)
- Link: https://doi.org/10.1002/eng2.70528
- Why it matters: pseudo-labeling plus contrastive learning on LABR gave 66.25 percent macro F1, offering us two concrete techniques for our imbalanced data and a realistic macro F1 reference point.
- Note: the Wiley page blocks automated checks, but the DOI is registered and confirmed via Crossref.

### 10. NADI 2024: The Fifth Nuanced Arabic Dialect Identification Shared Task

- Authors: Muhammad Abdul-Mageed, Amr Keleg, AbdelRahim Elmadany, Chiyu Zhang, Injy Hamed, Walid Magdy, Houda Bouamor, Nizar Habash
- Year: 2024
- Venue: Proceedings of ArabicNLP 2024, pages 709-728
- Link: https://aclanthology.org/2024.arabicnlp-1.79/
- Why it matters: an ensemble of ARBERT, MARBERT, and MARBERTv2 won at 50.57 macro F1 on multi-label dialect ID, giving us a proven ensemble fallback and a warning that multi-label scoring is much harsher than single-label.

### 11. Arabic Dialect Identification under Scrutiny: Limitations of Single-label Classification

- Authors: Amr Keleg and Walid Magdy
- Year: 2023
- Venue: Proceedings of ArabicNLP 2023, pages 385-398
- Link: https://arxiv.org/abs/2310.13661
- Why it matters: about 66 percent of apparent model errors were not true errors, so our audit should check disagreements with a native speaker before counting them as errors.

### 12. Yet Another Model for Arabic Dialect Identification

- Authors: Ajinkya Kulkarni and Hanan Aldarmaki
- Year: 2023
- Venue: Proceedings of ArabicNLP 2023, pages 435-440
- Link: https://aclanthology.org/2023.arabicnlp-1.37/
- Why it matters: ECAPA-TDNN with UniSpeech-SAT speech embeddings reached 84.7 percent on ADI-5 and 96.9 percent on ADI-17, showing pretrained speech embeddings are the right input if we ever add an audio branch.

### 13. Arabic Topic Detection: A Comprehensive Review of Recent Advances

- Authors: Noor S. Dawood and Salma A. Mahmood
- Year: 2025
- Venue: International Journal of Computational and Experimental Science and Engineering (IJCESEN), volume 11, number 3, pages 5541-5551
- Link: https://doi.org/10.22399/ijcesen.3424
- Why it matters: the survey confirms MARBERT beats AraBERT on dialectal text, ensembles beat single models, and data scarcity is the central Arabic NLP bottleneck, which supports prioritizing our labeling and audit quality over architecture tweaks.

### 14. From FusHa to Folk: Exploring Cross-Lingual Transfer in Arabic Language Models

- Authors: Abdulmuizz Khalak, Abderrahmane Issam, and Gerasimos Spanakis
- Year: 2026
- Venue: Proceedings of the Thirteenth Workshop on NLP for Similar Languages, Varieties and Dialects (VarDial), pages 196-209
- Link: https://arxiv.org/abs/2602.09826
- Why it matters: dialect-specific models beat general models only when supported by substantial dialect pretraining data, and MSA models sometimes outperform dialect models. That supports EgyBERT at 1.07 billion Egyptian tokens and works against small dialect models such as AraRoBERTa-EGY at 37.2 million tokens, so it belongs in the model selection reasoning.

---

## Sources

All 46 research notes are in the vault at `research/notes/`. Key model and method sources:

- EgyBERT model: https://huggingface.co/faisalq/EgyBERT (paper: https://arxiv.org/abs/2408.03524)
- MARBERTv2 model: https://huggingface.co/UBC-NLP/MARBERTv2 (paper: https://arxiv.org/abs/2109.01703)
- AraBERTv2 model: https://huggingface.co/aubmindlab/bert-base-arabertv2 (paper: https://arxiv.org/abs/2003.00104)
- CAMeLBERT-mix model: https://huggingface.co/CAMeL-Lab/bert-base-arabic-camelbert-mix (paper: https://arxiv.org/abs/2103.06678)
- AraModernBERT model: https://huggingface.co/NAMAA-Space/AraModernBert-Base-V1.0
- AraRoBERTa-EGY model: https://huggingface.co/reemalyami/AraRoBERTa-EGY (paper: https://aclanthology.org/2022.wanlp-1.18/)
- Egyptian XLS-R checkpoint: https://huggingface.co/IbrahimAmin/egyptian-arabic-wav2vec2-xlsr-53
- VarDial 2026 cross-lingual transfer paper: https://arxiv.org/abs/2602.09826
- XLS-R 300M model: https://huggingface.co/facebook/wav2vec2-xls-r-300m (paper: https://arxiv.org/abs/2111.09296)
- Whisper large-v3 model: https://huggingface.co/openai/whisper-large-v3 (paper: https://arxiv.org/abs/2212.04356)
- BERT paper: https://arxiv.org/abs/1810.04805
- RoBERTa paper: https://arxiv.org/abs/1907.11692
- MT-DNN paper: https://arxiv.org/abs/1901.11504
- Kendall uncertainty weighting: https://arxiv.org/abs/1705.07115
- GradNorm: https://arxiv.org/abs/1711.02257
- Focal loss: https://arxiv.org/abs/1708.02002
- Mosbach et al. 2021 fine-tuning stability: https://arxiv.org/abs/2006.03609
- HuBERT: https://arxiv.org/abs/2106.07447
- WavLM: https://arxiv.org/abs/2110.13900
- Hugging Face Trainer guide: https://huggingface.co/docs/transformers/en/main_classes/trainer

## Claims without a direct source

- The Moawad et al. 2025 accuracy of 87.64 percent comes from a secondary source (a literature review table), not from the paper text itself. Treat it as indicative.
- The Wiley DOI for Ezzeldin et al. 2025 is registered and confirmed via Crossref, but the Wiley page itself blocks automated checks, so the link was verified through the Crossref record rather than a direct page load.
- The KuralHub Arabic emotion benchmark figures (Whisper encoder 82.0 percent, WavLM large 71 percent, XLS-R 61 to 63 percent) come from the benchmark page, not from a peer reviewed paper.
