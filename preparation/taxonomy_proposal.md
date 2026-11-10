# Taxonomy proposal (candidates only)

Status: PROPOSED. Nothing here is a label. Every candidate needs team
approval and an annotation guide before any row is labeled. Method: TF-IDF
plus k-means on the 5,881 train-ready transcripts, k=10, seed 42,
scikit-learn 1.9.1. Silhouette scores on a 2000-row
sample: k=6 0.0079, k=8 0.0104, k=10 0.0127, k=12 0.0132, k=15 0.0144.
The scores are near zero, so separation is weak and one large general
cluster holds 2,424 rows (41 pct). The candidates below are a starting
point for annotation, not a final taxonomy.

## Candidate complaint categories

### billing and charges (proposed)

The customer questions a bill, a charge, or the price of a service.

Cluster 0, size 233. Top terms: فيها, خدمات, كبير, هل, الفاتوره, التحميل, الصبح, سرعه, بين, اصلا.

### general network and service complaint (proposed)

A general complaint about the network, the line, or the service with no narrower theme.

Cluster 1, size 2424. Top terms: التطبيق, اعرف, غير, حد, لو, الخدمه, الشبكه, وانا, عندي, الخط.

### app use and access attempts (proposed)

Repeated attempts to use the app, register, or complete a step in the app.

Cluster 2, size 469. Top terms: مره, اني, وكل, التطبيق, رغم, بيطلب, ليه, اول, امان, تسجيل.

### app login and account access (proposed)

The customer cannot log in to the app or reach their account.

Cluster 3, size 139. Top terms: الابليكيشن, دخلت, اعمل, الرقم, اساسا, بساعه, وبعدين, الحساب, اختفي, وبرضو.

### thanks or praise, not a complaint (proposed)

The message thanks the company or praises the service; it states no complaint.

Cluster 4, size 393. Top terms: شكرا, لكم, بجد, فعلا, الخدمه, لانكم, انكم, المشكله, السريع, الشكوي.

### branch or staff interaction (proposed)

The complaint is about a visit, a call, or something staff said or did.

Cluster 5, size 576. Top terms: طب, الموظف, لازم, قال, الفرع, ليه, خط, ازاي, قالولي, ولما.

### greeting only, no complaint stated (proposed)

The message is a greeting with no complaint stated.

Cluster 6, size 334. Top terms: عليكم, السلام, ليه, واحده, شكرا, الله, غير, ورحمه, لو, خدمه.

### balance and data consumption (proposed)

The customer questions balance, credit, or how fast data or credit is consumed.

Cluster 7, size 426. Top terms: حاجه, فجاه, اي, ومش, استهلاك, الرصيد, بقت, عارفين, وانا, غير.

### no reply or long wait (proposed)

The customer got no reply or waited a long time for an answer.

Cluster 8, size 401. Top terms: فيش, وما, اي, اسبوع, وسيله, رد, حد, وفجاه, شكوي, مشكله.

### cancellation request (proposed)

The customer asks to cancel a service or a subscription.

Cluster 9, size 486. Top terms: خدمه, معينه, غير, وانا, العمله, العملاء, الغاء, طلبت, مني, ليه.

## What the text cannot decide

Complaint urgency: the clusters carry no time or impact signal, so urgency
levels need human judgment and the annotation guide, not clusters.

Customer state: no cluster maps to a state class. State needs human
annotation under agreed definitions, with text and voice evidence kept
separate.

Churn risk: partially supported. The cancellation cluster (486 rows)
carries الغاء language; other departure terms are rare (counts in
cluster_results.json). Cancelling one service is not the same as leaving
the provider, so churn stays a candidate dimension, not a confirmed class.

Non-complaint messages: two clusters are not complaints at all (thanks or
praise, 393 rows; greeting only, 334 rows). The annotation guide must
cover them, or the classifier will force them into complaint classes.
