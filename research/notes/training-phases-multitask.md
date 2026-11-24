---
title: "Training phases and multi-task model evaluation for SVR"
tags: [training, phases, multi-task, model-selection, evaluation, svr]
source_url: "https://huggingface.co/learn/nlp-course/chapter3/3"
---

# Training phases and multi-task model evaluation for SVR

Sources: Hugging Face NLP Course Trainer chapter (https://huggingface.co/learn/nlp-course/chapter3/3) for the fine-tuning workflow; "Multi-Task BanglaBERT for Joint Sentiment and Fake News Detection" (https://zenodo.org/records/18649044/files/main.pdf) for the shared-encoder multi-task pattern with per-task losses; "A Multi-Task Learning Framework for Sentiment Analysis and News Classification for Low-Resource Language" (https://jobasrfudutsinma.com/index.php/ojs-files/article/download/348/306/655) for multi-task experiment design including class weighting, encoder freezing, and seed variation. Metric guidance is in the companion note training-metrics-imbalanced.md.

## Phase 0: Preparation and frozen checks

Before any training, verify the inputs and freeze them. Confirm the clean training tables and audio folders match (5,751 rows, train 4,031, validation 1,136, test 584). Record the label distribution and support per class in each split. Measure the token length distribution of the Whisper transcripts to set max sequence length (expect the 99th percentile well under 128 tokens). Confirm the saved class weights (churn at_risk 89.859, mad 7.234) match the training split frequencies. Freeze the splits: no re-splitting after results exist.

## Phase 1: Baseline (TF-IDF plus logistic regression)

Train one TF-IDF plus logistic regression model per field, with class_weight="balanced". This is cheap, fast, and gives a reference number every later model must beat. It also exposes data problems early: if the baseline beats a fine-tuned model on a field, the fine-tune is misconfigured, not the data. Report macro-F1 per field on validation. Keep the baseline code and its predictions so error analysis can compare baseline errors against transformer errors later.

## Phase 2: Single-task fine-tuning (reference models)

Fine-tune the chosen encoder (MARBERTv2 first) separately for each of the four fields. Use the recommended recipe: learning rate 2e-5, batch size 16, 3 epochs, warmup ratio 0.1, weight decay 0.01, max sequence length 128, AdamW, linear decay, class weights in the loss. Run 5 seeds and report mean plus standard deviation of macro-F1 per field on validation. These four single-task models are the reference the multi-task model must match or beat. They also isolate problems: if churn fails in the single-task setup, the cause is the rare class, not multi-task interference.

## Phase 3: Multi-task fine-tuning (the SVR model)

Architecture: one shared encoder with four task-specific classification heads (hard parameter sharing). This is the standard pattern in the multi-task literature: a shared encoder builds one representation, each head predicts one field. Loss: the sum of the four per-task cross-entropy losses, each with its own class weights. Start with equal task weights (1.0 each). If one task dominates training (its loss stays large while others converge), adjust task weights on validation only, or normalize each task loss by its number of classes. The BanglaBERT multi-task work used a weighted sum of task losses with per-task loss functions (focal loss for one task, weighted cross-entropy for the other); the Hausa AfriBERTa work tested class weighting, encoder freezing, gradual unfreezing, and dynamic loss weighting as separate experiments. For SVR, keep it simple: equal weights plus per-task class weights first, and treat task re-weighting as a later experiment only if validation shows interference.

Train with the same recipe as Phase 2, 5 seeds, early stopping on the mean validation macro-F1 across the four tasks (patience 2 epochs, maximum 5 epochs). Save the best checkpoint per seed by validation mean macro-F1.

## Phase 4: Validation, threshold tuning, and model selection

Evaluate on validation only. For each field, report macro-F1, macro-precision, macro-recall, per-class precision, recall, F1 with support, and the confusion matrix. Compare the multi-task model against the Phase 1 baseline and the Phase 2 single-task models field by field. Tune the churn decision threshold on validation using the precision-recall curve (see the metrics note). Select the final configuration on validation mean macro-F1, never on test. If the multi-task model is worse than a single-task model on a field by more than the seed standard deviation, that is task interference: consider training that field as a separate single-task model in production, or adjusting task weights and re-running Phase 3.

## Phase 5: Final test evaluation (once)

Run the selected model on the frozen test set (584 rows) exactly once and report the full per-field metric set. For churn, do not report test-only recall from the single at-risk row; report churn on validation plus test pooled with raw counts (see the metrics note). The test numbers are the headline results. No further tuning after this point; any change sends the model back to Phase 4.

## Phase 6: Error analysis and deployment readiness

Read the errors, do not only average them. Sample 50 errors per field from validation, group them by cause (transcription error, dialect wording, ambiguous label, genuinely hard case), and record the share of each cause. Check calibration of the churn probabilities if a threshold policy will use them. Measure inference latency and memory on the deployment hardware, since the ticket pipeline must keep up with incoming voicemails. Record the final model card: encoder, hyperparameters, seeds, validation and test metrics, threshold, and known limits.

## How to evaluate a multi-task model

Report per-task metrics first and always. The combined score, if one is needed, is the unweighted mean of the four per-task macro-F1 values. Label it as such and keep all four values visible next to it. Do not report a single combined number alone: it hides a failing task behind three good ones. Do not average accuracy across tasks either, for the same reason plus the imbalance problem. Also report, for transparency, whether each task is better, equal, or worse than its Phase 2 single-task reference, with the difference in macro-F1 points and the seed standard deviation, so a small difference is not mistaken for a real win.

## Assessment for SVR

The phase order protects the team from the two classic mistakes: tuning on test, and declaring victory from a single lucky run. The baseline in Phase 1 costs minutes and pays for itself the first time a fine-tune goes wrong. The single-task reference in Phase 2 is what makes the multi-task result interpretable. Five seeds per phase is affordable at this data size (about 252 steps per epoch) and is required by the stability literature. Total compute for the full plan is small: 3 encoders times 4 tasks times 5 seeds in Phase 2 is the largest block, and each run is minutes on one GPU.
