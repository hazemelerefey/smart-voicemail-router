# SVR `other` re-labeling report

Date: 2026-11-11. Scope: the 796 rows of `labeled_full_v1.csv` (5,881 train-ready rows) with `complaint_category == other` (13.5%). No model was trained. Source CSVs were not modified. Nothing was pushed to GitHub.

## Method

1. Joined the 796 `other` rows to `transcripts_clean.csv` on `file` (796/796 matched, no empty `text_norm`).
2. Clustered the 796 `text_norm` values with TF-IDF (3,000 features, 1-2 grams, min_df 2) + k-means, k = 6..12, seed 42. Silhouette on a fixed 700-row sample:
   k=6: 0.0222, k=7: 0.0237, k=8: 0.0285, k=9: 0.0323, k=10: 0.0303, k=11: 0.0348, k=12: 0.0368.
   Chosen k = 12 (highest silhouette, most interpretable micro-clusters). All scores are near zero, the same weak separation as the full-set clustering, so clustering was used only as a discovery aid: k=12 surfaced clean micro-clusters (second line on the same number, 31 rows; SIM moved to another device, 13; home-vs-mobile package comparison, 13; "general inquiries changed suddenly", 21) and two large diffuse clusters that needed reading, not clusters, to split.
3. Every candidate theme was then verified by reading the actual `text_norm` values and the annotator `note` on each row. Cluster assignment alone moved nothing. Keyword masks were built, their full hit lists were read row by row, false positives were removed (promo-spam rows out of offers, SIM-move rows out of porting, balance-transfer rows out of porting, garbled rows out of everything), and the final lists were re-checked.
4. A theme became a new category only if it had at least 60 verified rows AND was clearly distinct from the existing 10 categories. Ambiguous rows stayed in `other`.

## New categories proposed (2)

### offers_and_packages — 207 rows move here

Questions, comparisons, activation, renewal, change/switch and problems of packages, plans, offers and discounts, including student, family, kids, senior and small-business offers, discount eligibility, promised gifts/cashback never received, and plan/system changes. Distinct from `billing_and_charges` (disputes about charges already incurred) and `balance_and_data` (how fast credit/data is consumed): these rows ask about the product on offer, not about a bill or consumption.
Examples (real `text_norm`):
- "لماذا كلما حاولت ان استفيد من عرض جديد يظهر لي غير متاح حاليا رغم ان الرساله جاءت لي منكم"
- "هل تريد ان تفهم الفرق بين الباقه المائيه والباقه الاعلي"
- "كنت محتاج عرف لو في خصم خاص لزويا اللي احتاجات او كبر السن"

### sim_services — 61 rows move here

Questions and problems about the SIM and the line itself: a second line on the same number (31), moving the SIM to another device (13), new-SIM activation and delivery delay, lost-SIM blocking failures, SIM not supported / heating, SIM-swap errors, two lines on one national ID. Distinct from `network_and_connectivity` (service quality) and `app_and_account`.
Examples (real `text_norm`):
- "كنت محتاجه عرف هل ممكن اعمل خط تاني بنفس الرقم القديم"
- "كنت محتاجه عرف هل ممكن اعمل خط بنفس الرقم القديم"
- "صغر بسيط لو نقلت شريحتي لجهاز تاني هل الباقه تشتغل عادي"

## Result

- Move out of `other`: 268 rows (33.7% of the bucket) — 207 to `offers_and_packages`, 61 to `sim_services`.
- Stay in `other`: 528 rows (66.3%).
- `other` would shrink from 796 rows (13.5% of train-ready) to 528 rows (9.0%) if these labels are adopted.
- No row outside the `other` bucket was touched. Urgency, customer state and churn risk were not changed.

## Themes that stay in `other` (with counts)

| Theme | Rows | Why it stays |
|---|---|---|
| garbled_or_unclear | 151 | Transcript too garbled / too short to label. Needs better audio, not a category. |
| other_mixed | 141 | Long tail, each topic under ~12 rows (plan-change procedure tied to branch visits, international/roaming, accessibility/sign-language, branch appointment booking, call recording, caller tune, balance caps, usage checks, support hours, contact channels). |
| spam_and_harassment | 53 | Coherent (unwanted promo/marketing calls and messages that will not stop, harassing international calls, scam prize calls, own number blocked for suspected spam) but below the 60-row bar. Revisit if it grows. |
| vague_general_complaint | 44 | Readable but non-specific (service got worse, new problems every day, sudden unexplained changes). No carve-out. |
| loyalty_and_rewards | 39 | Coherent (how to use points, points reset to zero, rewards unavailable) but below the 60-row bar. |
| number_porting | 30 | Coherent (porting to/from another provider, line-ownership transfer, portability refusals) but below the 60-row bar. Revisit if it grows. |
| router_and_devices | 28 | Coherent (router instalments, missing manual/cable, used or faulty router) but below the 60-row bar. |
| payment_methods | 26 | Only 26 rows, and it overlaps `billing_and_charges`, so it fails distinctness too. |
| family_and_children | 16 | Small once family-package questions are counted under offers (parental controls, kids educational service not working, guardianship rules, balance transfer to children). |

Notes for the team: the 26 `payment_methods` rows and the usage-check rows inside `other_mixed` are arguably `billing_and_charges` / `balance_and_data` material; they were left in `other` because this task only authorizes moves to new categories, but a reviewer may move them to the existing categories instead. Two further garbled rows look porting-related per their annotator notes but were kept in `garbled_or_unclear` because the transcripts themselves are unreadable.

## Caveats

- `sim_services` clears the 60-row bar by exactly one row (61). The count is exact and every row was read, but it is marginal: if the team applies a stricter reading (e.g. excluding the 2 SIM-heating rows as device questions), it falls to 59 and should stay in `other`. Flagging this rather than hiding it.
- `offers_and_packages` is broad by design (the whole product catalogue: offers, packages, plans, discounts). If the team wants finer splits later (e.g. a separate discounts category), the `theme` column in `other_relabel.csv` does not split it; the split would need a second pass.
- Clustering silhouette near zero (best 0.0368 at k=12) confirms the transcripts separate weakly; the labels above rest on human reading of all 796 rows, not on the clusters.

## greeting_only recommendation

Drop `greeting_only` from the taxonomy. It has 0 rows in `labeled_full_v1.csv` (verified by count), so it is a dead label: no training signal, and keeping it invites annotators to use it for rows that belong elsewhere. If genuine greeting-only voicemails appear in future data, re-add it then.

## Outputs

- `dataset/prepared/other_relabel.csv` — 796 rows, columns `file, old_category, new_category, theme, note`.
- `dataset/prepared/other_themes.json` — 11 themes with counts, proposed category (or null), 3 real example texts each, and the decision reason.
- This report: `dataset/prepared/other_relabel_report.md`.

Adoption note: the taxonomy proposal says any change after calibration needs Hazem's approval. These two new categories (and the `greeting_only` drop) are proposals for that approval, not applied changes: `labeled_full_v1.csv` itself was left untouched.
