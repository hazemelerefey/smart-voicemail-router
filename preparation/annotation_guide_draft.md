# Annotation guide (DRAFT)

Status: DRAFT, proposed. Nothing here is approved. The team must agree the
candidate values and these rules before anyone labels a row. Fields follow
PRD v1.2 section 3: complaint_category, complaint_urgency, and
customer_state_text are separate fields and must never be used as synonyms.
Urgency is about the complaint, not the mood. State is about the customer,
not the complaint. A cancellation threat is evidence to assess, not an
automatic urgency label.

## Fields and candidate values

### complaint_category (proposed candidates from clustering, Task 3)

- billing and charges: The customer questions a bill, a charge, or the price of a service. (cluster 0, 233 rows)
- general network and service complaint: A general complaint about the network, the line, or the service with no narrower theme. (cluster 1, 2424 rows)
- app use and access attempts: Repeated attempts to use the app, register, or complete a step in the app. (cluster 2, 469 rows)
- app login and account access: The customer cannot log in to the app or reach their account. (cluster 3, 139 rows)
- thanks or praise, not a complaint: The message thanks the company or praises the service; it states no complaint. (cluster 4, 393 rows)
- branch or staff interaction: The complaint is about a visit, a call, or something staff said or did. (cluster 5, 576 rows)
- greeting only, no complaint stated: The message is a greeting with no complaint stated. (cluster 6, 334 rows)
- balance and data consumption: The customer questions balance, credit, or how fast data or credit is consumed. (cluster 7, 426 rows)
- no reply or long wait: The customer got no reply or waited a long time for an answer. (cluster 8, 401 rows)
- cancellation request: The customer asks to cancel a service or a subscription. (cluster 9, 486 rows)

Two candidates are not complaints at all (thanks or praise; greeting only).
Label them as such instead of forcing them into a complaint class. Rows that
fit no candidate get complaint_category = unclear and go to adjudication.

### complaint_urgency (proposed)

- urgent: the complaint states a service outage, a total loss of service, or
  a time-bound harm if not fixed now (for example, a line cut before an
  exam or a payment deadline). Judge the complaint, not the tone.
- standard: a real problem with no stated time-bound harm.
- low: a question, a request, or a minor inconvenience with no service impact.
- unclear: the transcript does not say enough to judge. Goes to adjudication.

Urgency is never inferred from anger alone. An angry customer with a routine
question is standard urgency with an angry state. A calm customer reporting
a total outage is urgent with a calm state. That distinction is the point
of keeping the fields separate (PRD risk R3).

### customer_state_text (proposed)

- calm: the words are neutral and the request is stated plainly.
- dissatisfied: the words express frustration or disappointment without
  threats or raised demands.
- angry: the words express anger, blame, or demands in strong terms.
- distressed: the words express worry, helplessness, or fear about the issue.
- unclear: the transcript does not say enough to judge. Goes to adjudication.

State comes from words only in this guide. Voice evidence is a separate
field (voice_state_candidate) and is never mixed into customer_state_text.

### churn_risk (optional, proposed)

- yes: the customer states they will leave the provider or cancel their line.
- no: no departure language is present.
- unclear: ambiguous. Goes to adjudication.

Cancelling one service or add-on is not churn. Only leaving the provider counts.

## Egyptian-dialect glossary (from the audit, counts included)

Frequent Arabic words in the train-ready transcripts (single terms):

- في: 2473
- من: 2044
- مش: 1715
- انا: 1469
- ما: 1176
- كل: 1153
- ان: 964
- لي: 925
- علي: 921
- لما: 791
- جدا: 730
- خدمه: 712
- ده: 644
- اي: 612
- بعد: 611

Frequent Latin telecom terms (single terms):

- otp: 6
- g: 5
- me: 4
- back: 4
- call: 4
- application: 3
- vpn: 3
- online: 2
- control: 2
- flex: 2
- logout: 2
- only: 2
- volt: 1
- clm: 1
- sms: 1

The glossary is a count, not an agreement. The team must agree the final
glossary before any external text call (PRD FR-04).

## Worked examples (field plus reason only, no transcript quotes)

- Example A: category = balance and data consumption. Reason: the customer
  questions why credit ran out. Urgency = standard. Reason: no outage is
  stated. State = dissatisfied. Reason: the words express frustration.
- Example B: category = app login and account access. Reason: the customer
  cannot enter the app. Urgency = standard. Reason: the account is
  unreachable but no time-bound harm is stated. State = calm. Reason: the
  request is stated plainly.
- Example C: category = cancellation request. Reason: the customer asks to
  cancel a service. Urgency = low. Reason: a cancellation request is not
  time-bound harm. State = calm. Reason: neutral words. Churn = unclear.
  Reason: cancelling one service is not leaving the provider.
- Example D: category = thanks or praise, not a complaint. Reason: the
  message only thanks the company. Urgency = low. State = calm.
- Example E: category = unclear. Reason: the transcript is too short or too
  garbled to tell what the complaint is. Goes to adjudication.

## Double annotation and adjudication

Two annotators label every row independently. They never see each other's
labels. Rows where they disagree go to an adjudicator, who decides and
records the reason. The adjudicator is named by the team before annotation
starts. Unclear rows are adjudicated, never guessed.

## Calibration batch

100 rows: 90 stratified across the 10 clusters plus 10 flagged rows from
quarantine. File IDs are in dataset/prepared/calibration_batch.json.
Both annotators label the batch first. Agreement target before scaling:
Cohen's kappa at least 0.7 per field (category, urgency, state). If any
field is below 0.7, revise this guide and re-run calibration. Do not scale
annotation on a failing calibration.

## Who annotates

Open decision. The team names the annotators and the adjudicator before
annotation starts. The audio-speech pair does not annotate its own audit.
