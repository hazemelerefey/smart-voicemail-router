# Annotation guide v1 (APPROVED)

Status: APPROVED guide v1, 2026-11-11, approved by Hazem. Annotators:
Hazem and Ebtihal. Adjudicator: Hazem, who is also the project reviewer.
Fields follow PRD v1.2 section 3: complaint_category,
complaint_urgency, and customer_state are separate fields and must never
be used as synonyms. Urgency is about the complaint, not the mood.
State is about the customer, not the complaint. A cancellation threat is
evidence to assess, not an automatic urgency label.

## Fields and values

### complaint_category (10 values, approved taxonomy)

- network_and_connectivity: A general complaint about the network, the
  line, or the service with no narrower theme. (cluster 1, 2424 rows)
- billing_and_charges: The customer questions a bill, a charge, or the
  price of a service. (cluster 0, 233 rows)
- balance_and_data: The customer questions balance, credit, or how fast
  data or credit is consumed. (cluster 7, 426 rows)
- app_and_account: The customer cannot use the app, log in, register,
  or reach their account. (clusters 2 and 3, 608 rows)
- branch_and_staff: The complaint is about a visit, a call, or
  something staff said or did. (cluster 5, 576 rows)
- no_reply_or_long_wait: The customer got no reply or waited a long
  time for an answer. (cluster 8, 401 rows)
- cancellation_request: The customer asks to cancel a service or a
  subscription. (cluster 9, 486 rows)
- thanks_or_praise: The message thanks the company or praises the
  service; it states no complaint. (cluster 4, 393 rows)
- greeting_only: The message is a greeting with no complaint stated.
  (cluster 6, 334 rows)
- other: The complaint fits none of the nine values above. Write a
  short note saying what it is.

Two categories are not complaints at all (thanks_or_praise;
greeting_only). Label them as such instead of forcing them into a
complaint class. Rows that fit no candidate get complaint_category =
other with a note, and go to adjudication.

### complaint_urgency (3 values)

- high: service fully down, money lost, repeated failure, or stated
  time-bound harm if not fixed now. Judge the complaint, not the tone.
- medium: degraded service, a billing dispute, or a long wait with a
  real problem behind it.
- low: a question, a request, thanks, or a greeting, with no service
  impact.

Urgency is never inferred from anger alone. An angry customer with a
routine question is medium urgency with a mad state. A calm customer
reporting a total outage is high urgency with a calm state. That
distinction is the point of keeping the fields separate (PRD risk R3).
If the transcript says too little to judge urgency, choose low and the
row goes to adjudication.

### customer_state (5 values)

- calm: the words are neutral and the request is stated plainly.
- frustrated: the words express frustration or disappointment without
  threats or strong demands.
- mad: the words express anger, blame, or demands in strong terms.
- satisfied: the words express thanks, praise, or contentment.
- unclear: the transcript does not say enough to judge. Goes to
  adjudication.

State comes from words only in this guide. Voice evidence is a separate
field (voice_state_candidate) and is never mixed into customer_state.

### churn_risk (2 values)

- at_risk: the customer states they will leave the provider or close
  their line, in explicit words.
- not_at_risk: no departure language is present.

Cancelling one service or add-on is not churn. Only leaving the
provider counts.

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

- Example A: category = balance_and_data. Reason: the customer
  questions why credit ran out. Urgency = medium. Reason: no outage is
  stated. State = frustrated. Reason: the words express frustration.
- Example B: category = app_and_account. Reason: the customer cannot
  enter the app. Urgency = medium. Reason: the account is unreachable
  but no time-bound harm is stated. State = calm. Reason: the request
  is stated plainly.
- Example C: category = cancellation_request. Reason: the customer asks
  to cancel a service. Urgency = low. Reason: a cancellation request is
  not time-bound harm. State = calm. Reason: neutral words. Churn =
  not_at_risk. Reason: cancelling one service is not leaving the
  provider.
- Example D: category = thanks_or_praise. Reason: the message only
  thanks the company. Urgency = low. State = satisfied.
- Example E: category = other. Reason: the transcript is too short or
  too garbled to tell what the complaint is. Goes to adjudication.

## Double annotation and adjudication

Two annotators label every row independently. They never see each
other's labels. Rows where they disagree go to the adjudicator, who
decides and records the reason. Unclear rows are adjudicated, never
guessed.

## Calibration batch

100 rows: 90 stratified across the 10 clusters plus 10 flagged rows from
quarantine. File IDs are in dataset/prepared/calibration_batch.json.
Both annotators label the batch first. Agreement target before scaling:
Cohen's kappa at least 0.7 per field (category, urgency, state). If any
field is below 0.7, revise this guide and re-run calibration. Do not
scale annotation on a failing calibration.

## Who annotates

Annotators: Hazem and Ebtihal. Adjudicator: Hazem. Label Studio project:
SVR calibration, running on the VM. Labels live in Label Studio; the
gold test set is purely human labeled and never used for training.
