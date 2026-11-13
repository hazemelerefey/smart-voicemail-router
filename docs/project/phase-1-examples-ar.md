# أمثلة حقيقية: دور حازم ودور آية في المرحلة الأولى

**Document ID:** SVR-PHASE-01-EX

**Version:** 1.0

**Updated:** 12 November 2026

## الفكرة في سطر واحد

حازم بيبني التدريب وبيقرر. آية بتبني القياس وبتثبت الأرقام.

## دور حازم: Training Lead

حازم صاحب مجهود التدريب كله والـ model النهائي. هو اللي بيبني الـ training pipeline، وبيملك الـ dataset، وبياخد القرارات، وبيراجع وبيدمج شغل كل عضو.

### مثال حقيقي: الـ training notebook skeleton

حازم بيكتب الـ training notebook skeleton اللي كل دور بيستخدمه. الـ notebook ده بيعمل كده:

1. بيحمّل التلات جداول النضيفة من `svr-data/final/`:
   - `clean_training_train.csv`، عدد الصفوف ⁦3,575⁩.
   - `clean_training_val.csv`، عدد الصفوف ⁦1,003⁩.
   - `clean_training_test.csv`، عدد الصفوف 518.
2. بيتأكد إن فولدرات الـ audio مطابقة: `dataset/train/` فيه ⁦3,575⁩ ملف WAV، و `dataset/val/` فيه ⁦1,003⁩ ملف، و `dataset/test/` فيه 518 ملف.
3. بيحدد الـ shared config اللي كل دور بيستخدمها: seed 42، و max sequence length 128، والتقسيم 70/20/10، ونسخة الـ dataset v2.
4. الـ notebook ده هو الهيكل. لمى وسيرا وآية كلهم بيبنوا عليه. محدش بيبني على setup مختلف.

اتشال أسوأ 655 transcript من الـ clean set، لأن الـ Whisper logprob بتاعها أقل من -0.30.

### مثال حقيقي: المراجعة والدمج

سيرا بتخلص التحقق من الـ audio، ولمى بتخلص الـ single-task setup، وآية بتخلص الـ infrastructure. كل واحدة بتدفع شغلها على الـ branch بتاع دورها. حازم بيراجع كل شغل من دول، ولو صح بيدمجه في `develop`. مفيش حاجة بتوصل لـ `develop` من غير مراجعته.

## دور آية: ML Infrastructure and Evaluation Engineer

آية صاحبة الـ machine اللي بتخلي التدريب موثوق فيه. هي اللي بتبني الـ infrastructure اللي كل الناس بتشغل عليها، والتقييم اللي بيثبت إذا كانت الـ models شغالة ولا لأ.

### مثال حقيقي: الـ config format

آية بتحدد صيغة الـ config اللي كل تجربة بتستخدمها. ملف config حقيقي شكله كده:

- model: EgyBERT
- learning rate: 2e-5
- batch size: 16
- epochs: 3
- seed: 42
- dataset version: v2
- split: train

كل تجربة بتستخدم نفس الصيغة دي. مفيش تجربة بتسجل الـ config بتاعتها بطريقة مختلفة.

### مثال حقيقي: الـ run record

كل تجربة ليها run record. الـ record ده بيقول:

- run ID: 001
- hypothesis: EgyBERT بيتفوق على MARBERTv2 في complaint_category
- changed factor: الـ model
- held constant: learning rate 2e-5 و batch 16 و epochs 3
- measures: الـ macro-F1 لكل field
- artifacts: الـ checkpoint وملف التنبؤات

لو غيّرت الـ learning rate، الـ record بيقول كده، وباقي العوامل ثابتة. لو غيّرت أكتر من عامل في نفس الوقت، مش هتعرف أي واحد فيهم هو اللي عمل الفرق.

### مثال حقيقي: الـ evaluation harness

آية بتبني الـ evaluation harness. دي دالة بتاخد model مدرب و split، وبتشغله، وبتطلع per-field macro-F1 والـ accuracy والـ confusion matrix، بصيغة مخرجات ثابتة. هي بتبنيه على fixtures الأول، بـ mock predictions، عشان يشتغل قبل ما أي model حقيقي يبقى موجود. كل الناس بتقيس بنفس الطريقة.

### مثال حقيقي: الـ TF-IDF baseline

آية بتشغل الـ TF-IDF baseline. ده TF-IDF features مع logistic regression، model واحد لكل field، متدرب على الـ ⁦3,575⁩ صف بتوع الـ train، ومتقيّم على الـ ⁦1,003⁩ صف بتوع الـ validation. هي بتسجل الـ validation macro-F1 لكل field. الـ baseline ده هو المرجع اللي الـ neural models لازم تتفوق عليه.

## فين بيتقابلوا

آية بتسلم الـ infrastructure بدري في المرحلة الأولى. حازم ولمى وسيرا بيشتغلوا عليها. آية مش بتدرب الـ models. حازم مش بيبني نظام التتبع. حازم بيبني التدريب. آية بتبني القياس.

## الخلاصة

| | حازم | آية |
|---|---|---|
| بيبني إيه | الـ training pipeline والـ notebooks | الـ infrastructure والـ evaluation harness |
| بيملك إيه | الـ dataset والـ model النهائي | الـ TF-IDF baseline والتقارير |
| بيقرر إيه | الـ winner model والـ split freeze | مفيش قرارات، بس الأرقام |
| بيقيس إيه | بيراجع شغل كل عضو | بتقيس كل model بنفس الطريقة |

حازم بيطبخ الطبق. آية بنت الميزان وورقة التقييم، وبتدوق كل طبق بنفس الطريقة.
