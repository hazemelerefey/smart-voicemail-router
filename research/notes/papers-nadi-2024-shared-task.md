---
title: "NADI 2024: The Fifth Nuanced Arabic Dialect Identification Shared Task"
tags: [arabic-dialect, nadi, shared-task, marbert, ensemble, svr-literature]
source_url: "https://www.pure.ed.ac.uk/ws/portalfiles/portal/474659143/AbdulMageedEtalArabicNLP2024NADI2024TheFifthNuanced_final_pub_vers_con_contrib_.pdf"
---

# NADI 2024: The Fifth Nuanced Arabic Dialect Identification Shared Task

- Authors: Muhammad Abdul-Mageed, Amr Keleg, AbdelRahim Elmadany, Chiyu Zhang, Ines Hamed, Walid Magdy, Houda Bouamor, Nizar Habash
- Year: 2024
- Venue: Proceedings of ArabicNLP 2024, pages 709-728

## What they did

This is the official overview of the fifth NADI shared task. For the first time, dialect identification was cast as a multi-label task (Subtask 1), following the 2023 finding that single labels are incomplete. Subtask 2 asked for the Arabic Level of Dialectness (ALDi) as a regression score, and Subtask 3 was dialect-to-MSA machine translation. A total of 51 teams registered and 12 teams participated with 76 valid submissions.

## Model

The winning team (ELYADATA) used an ensemble of fine-tuned BERT-based Arabic models: ARBERT, MARBERT, and MARBERTv2, combined with a max-probabilities ensemble. Other teams used n-gram TF-IDF, classical machine learning, neural networks, pretrained language models, adapters, and data augmentation.

## Dataset

NADI 2024 multi-label country-level dialect data (8 dialects in the development set, 18 in the full task history). The shared task data is tweet text with multi-label dialect annotations.

## Results

- Subtask 1 (multi-label dialect identification): winning macro F1 of 50.57 percent (ELYADATA ensemble)
- Subtask 2 (level of dialectness): best RMSE of 0.1403
- Subtask 3 (dialect to MSA translation): best BLEU of 20.44
- For comparison, the best single-label NADI system in 2023 reached 87.27 percent macro F1, which shows how much harder honest multi-label scoring is

## Lesson for SVR

Four takeaways. First, the ensemble result is the strongest practical signal: combining ARBERT, MARBERT, and MARBERTv2 beat every single model, so if our single-model results plateau, a small ensemble of Arabic encoders is a proven next step. Second, the drop from 87 percent single-label F1 to 51 percent multi-label F1 is a warning about metric comparability: scores from different label framings cannot be compared, so our reported numbers must always state the framing and the averaging (macro F1 per task). Third, the level-of-dialectness subtask is a useful idea for us: a continuous dialectness or confidence score per transcript could flag low-confidence voicemails for human review instead of forcing a hard label. Fourth, the shared task confirms that dialect identification on short texts remains unsolved even for the best teams, which supports our choice not to add dialect identification as a fifth SVR label.

## Source

https://www.pure.ed.ac.uk/ws/portalfiles/portal/474659143/AbdulMageedEtalArabicNLP2024NADI2024TheFifthNuanced_final_pub_vers_con_contrib_.pdf
