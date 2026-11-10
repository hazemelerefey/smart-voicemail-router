# Taxonomy (approved)

Status: APPROVED by Hazem, 2026-11-11. These are the final label values
for the calibration batch and the first annotation round. Method: TF-IDF
plus k-means on the 5,881 train-ready transcripts, k=10, seed 42,
scikit-learn 1.9.1. Silhouette scores on a 2000-row sample: k=6 0.0079,
k=8 0.0104, k=10 0.0127, k=12 0.0132, k=15 0.0144. The scores are near
zero, so separation is weak and one large general cluster holds 2,424
rows (41 pct). Calibration will test whether that cluster splits; the
taxonomy is final for calibration, not frozen forever. Any change after
calibration needs Hazem's approval.

## complaint_category (10 values)

### network_and_connectivity

A general complaint about the network, the line, or the service with no
narrower theme. Cluster 1, size 2424. Top terms: التطبيق, اعرف, غير, حد,
لو, الخدمه, الشبكه, وانا, عندي, الخط. This cluster is 41 pct of the
train-ready rows. Calibration samples it heavily and tests whether it
breaks into narrower themes (outage, slow internet, no service). If it
does not split cleanly, it stays one category and the imbalance is
recorded.

### billing_and_charges

The customer questions a bill, a charge, or the price of a service.
Cluster 0, size 233. Top terms: فيها, خدمات, كبير, هل, الفاتوره,
التحميل, الصبح, سرعه, بين, اصلا.

### balance_and_data

The customer questions balance, credit, or how fast data or credit is
consumed. Cluster 7, size 426. Top terms: حاجه, فجاه, اي, ومش, استهلاك,
الرصيد, بقت, عارفين, وانا, غير.

### app_and_account

The customer cannot use the app, log in, register, or reach their
account. Merges the two app clusters, use and access attempts (cluster
2, 469 rows) and login and account access (cluster 3, 139 rows), total
608, because annotators cannot tell them apart reliably.

### branch_and_staff

The complaint is about a visit, a call, or something staff said or did.
Cluster 5, size 576. Top terms: طب, الموظف, لازم, قال, الفرع, ليه, خط,
ازاي, قالولي, ولما.

### no_reply_or_long_wait

The customer got no reply or waited a long time for an answer. Cluster
8, size 401. Top terms: فيش, وما, اي, اسبوع, وسيله, رد, حد, وفجاه,
شكوي, مشكله.

### cancellation_request

The customer asks to cancel a service or a subscription. Cluster 9,
size 486. Top terms: خدمه, معينه, غير, وانا, العمله, العملاء, الغاء,
طلبت, مني, ليه.

### thanks_or_praise

The message thanks the company or praises the service; it states no
complaint. Cluster 4, size 393. Top terms: شكرا, لكم, بجد, فعلا,
الخدمه, لانكم, انكم, المشكله, السريع, الشكوي.

### greeting_only

The message is a greeting with no complaint stated. Cluster 6, size
334. Top terms: عليكم, السلام, ليه, واحده, شكرا, الله, غير, ورحمه, لو,
خدمه.

### other

The complaint fits none of the nine values above. The annotator writes
a short note saying what it is, so new themes surface instead of
vanishing into other. No cluster supports this value; it is the escape
hatch for the long tail.

## complaint_urgency (3 values)

Judged from the complaint only, never from the tone.

- high: service fully down, money lost, repeated failure, or stated
  time-bound harm if not fixed now.
- medium: degraded service, a billing dispute, or a long wait with a
  real problem behind it.
- low: a question, a request, thanks, or a greeting, with no service
  impact.

## customer_state (5 values)

State comes from words only. Voice evidence is a separate field
(voice_state_candidate) and is never mixed into customer_state.

- calm: the words are neutral and the request is stated plainly.
- frustrated: the words express frustration or disappointment without
  threats or strong demands.
- mad: the words express anger, blame, or demands in strong terms.
- satisfied: the words express thanks, praise, or contentment.
- unclear: the transcript does not say enough to judge. Goes to
  adjudication.

Why these five: mad, satisfied, and unclear are Hazem's words, unclear
is his escape hatch so no one is forced to guess. Calm and frustrated
were added because most voicemails sit between the poles: plain problem
statements and dissatisfied-but-not-mad complaints would otherwise be
forced into mad or satisfied and corrupt the labels.

## churn_risk (2 values)

- at_risk: the customer states they will leave the provider or close
  their line, in explicit words.
- not_at_risk: no departure language is present.

Cancelling one service or add-on is not churn. Only leaving the
provider counts.

## What the text cannot decide

Complaint urgency: the clusters carry no time or impact signal, so the
three urgency values rest on human judgment under the guide, not on
clusters.

Customer state: no cluster maps to a state class. State is annotated by
humans under the definitions above.

Non-complaint messages: two clusters are not complaints at all (thanks
or praise, 393 rows; greeting only, 334 rows). They are categories of
their own so the classifier never forces them into complaint classes.
