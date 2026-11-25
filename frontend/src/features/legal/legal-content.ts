export interface LegalHighlight {
  label: string
  value: string
}

export interface LegalTable {
  headers: string[]
  rows: string[][]
}

export interface LegalSection {
  id: string
  title: string
  paragraphs: string[]
  bullets?: string[]
  table?: LegalTable
}

export interface LegalDoc {
  eyebrow: string
  title: string
  subtitle: string
  docId: string
  version: string
  effectiveDate: string
  framework: string
  deployment: string
  highlights: LegalHighlight[]
  sections: LegalSection[]
}

export const PRIVACY_DOC: Record<'en' | 'ar', LegalDoc> = {
  en: {
    eyebrow: 'Data Protection & Sovereign AI Notice',
    title: 'Privacy Policy',
    subtitle:
      'Governs how SVR System (Smart Voicemail Router) ingests, encrypts, transcribes, classifies, retains, and protects subscriber voicemail records and operator account data within self-hosted telecom customer-care infrastructure.',
    docId: 'SVR-PRIVACY-2026',
    version: 'v1.0',
    effectiveDate: '26 Nov 2026',
    framework: 'Egyptian Law No. 151 of 2020 & NTRA Safeguards',
    deployment: 'Single-Tenant Self-Hosted',
    highlights: [
      { label: 'Third-Party AI Transfer', value: '0% External Egress' },
      { label: 'Audio Encryption at Rest', value: 'Fernet AES-128 + HMAC' },
      { label: 'Default Audio Retention', value: '90 Days (Configurable)' },
      { label: 'Session Timeout', value: '8 Hours HttpOnly' },
    ],
    sections: [
      {
        id: 'scope',
        title: 'Scope, Data Controller Role & Regulatory Alignment',
        paragraphs: [
          'This Privacy Policy applies to all processing of subscriber voicemail recordings, speech-to-text transcripts, structured triage classifications, callback routing records, operator accounts, and audit logs performed through SVR System ("the Platform").',
          'The telecom customer-care organization operating the deployment acts as the Data Controller under the Egyptian Personal Data Protection Law (Law No. 151 of 2020) and applicable National Telecom Regulatory Authority (NTRA) confidentiality rules. SVR System is architected as a limited-risk decision-support platform that prepares and routes internal callback tickets for human specialists; it never executes automated legal or financial decisions and never initiates automated outbound contact to subscribers.',
        ],
        bullets: [
          'Pre-production validation and quality benchmarking rely exclusively on the consented SVR Voicemail Corpus (acted recordings containing zero live subscriber personal data).',
          'Live subscriber voicemail ingestion is permitted only after the operating organization completes formal Data Protection Officer (DPO) and legal counsel sign-off.',
        ],
      },
      {
        id: 'inventory',
        title: 'Personal Data Inventory & Processing Purposes',
        paragraphs: [
          'We process only the minimum categories of personal and operational data strictly necessary to transcribe Arabic and code-switched telecom voicemails, prioritize callback queues, assign qualified care specialists, and maintain verifiable compliance records.',
        ],
        table: {
          headers: ['Data Category', 'Stored Fields', 'External AI Transfer', 'Retention', 'Lawful Basis'],
          rows: [
            [
              'Voicemail Audio Recordings',
              'Encrypted WAV, MP3, or M4A bytes (<= 25 MB, <= 60 s), duration, SHA-256 digest',
              'No (local Whisper large-v3)',
              '90 days default (configurable)',
              'Subscriber consent / telecom service care',
            ],
            [
              'Transcripts & STT Metadata',
              'Verbatim Arabic transcript, normalized text_norm, language mix, segment log-probabilities',
              'No (processed locally)',
              '90 days default (linked to ticket)',
              'Subscriber consent / service fulfillment',
            ],
            [
              'Ticket & AI Classification Records',
              'Category, urgency, customer state, churn risk, probability vectors, confidence, priority score, brief',
              'No (local 4x MARBERTv2)',
              '90 days default (linked to ticket)',
              'Telecom care triage & SLA management',
            ],
            [
              'Operator & Agent Accounts',
              'Work email, full name, bcrypt hash, role, assigned telecom skills, shift status, session hash',
              'No',
              'Active employment / assignment',
              'Employment / operational contract',
            ],
            [
              'Immutable Audit Events',
              'Actor email, entity ID, action, old/new JSON diff, UTC timestamp',
              'No',
              'Compliance policy retention',
              'Legal accountability & security',
            ],
          ],
        },
      },
      {
        id: 'residency',
        title: 'Zero Third-Party AI Transfer & Data Residency',
        paragraphs: [
          'Voice recordings inherently carry biometric and personal identifiers. SVR System eliminates external AI vendor exposure by executing all speech recognition (faster-whisper Whisper large-v3) and all four natural-language classification heads (UBC-NLP/MARBERTv2) strictly inside the operator private container network.',
          'All application services (database, cache, API server, AI worker, operator console, and observability stack) communicate over an isolated internal network on servers and encrypted volumes controlled by the operating organization, satisfying cross-border transfer restrictions under Articles 14 through 16 of Law No. 151 of 2020.',
        ],
        bullets: [
          'Zero raw audio, normalized transcripts, or ticket metadata are transmitted to external LLM APIs or cloud STT providers.',
          'Subscriber recordings are never used to train external commercial foundation models.',
          'Any future approved external text integration remains strictly prohibited from transmitting raw audio and requires local identifier redaction plus formal written authorization.',
        ],
      },
      {
        id: 'oversight',
        title: 'Automated Triage, Human Oversight & Non-Automated Decisions',
        paragraphs: [
          'Every automated classification output is treated as decision support for trained customer-care personnel rather than a final autonomous determination. Priority placement follows a transparent, deterministic 1-to-6 formula derived from urgency, churn risk, and emotional state.',
        ],
        bullets: [
          'Confidence Gating: Predictions falling below the configured confidence threshold (default 50%) or missing a required label automatically escalate to the Human Routing Queue.',
          'Human Review & Overrides: Supervisors can inspect raw encrypted audio, correct any automated label with live priority impact preview, and preserve explicit model versus human provenance.',
          'Automatic Routing Pause: Administrators can pause automated assignment globally at any time so all incoming voicemails route directly to supervisor review.',
          'Weekly Quality Sampling: Supervisors audit a recurring sample of high-confidence tickets to detect drift and verify classification accuracy.',
        ],
      },
      {
        id: 'security',
        title: 'Cryptographic & Technical Security Safeguards',
        paragraphs: [
          'SVR System enforces defense-in-depth protections across storage, transport, authentication, and browser delivery.',
        ],
        bullets: [
          'Encryption at Rest: Every uploaded or recorded voicemail file is encrypted with Fernet (AES-128-CBC with PKCS7 padding and HMAC-SHA256 authentication) before touching disk. Decryption occurs strictly in memory during transcription or authorized playback.',
          'Encrypted Backups: Scheduled backups bundle a SHA-256 manifest, encrypt the archive with Fernet, and emit an independent outer checksum sidecar verified before restoration.',
          'Transport Security: Production deployments enforce TLS 1.2 or higher with HTTP Strict Transport Security (HSTS) and Secure cookie attributes.',
          'Credential & Session Protection: Operator passwords are hashed with bcrypt (cost factor 12) against a breached-password denylist. Server-tracked sessions expire after 8 hours of inactivity and are immediately revoked upon sign-out, deactivation, or role changes.',
          'Request Integrity: All state-changing API mutations validate double-submit CSRF tokens using constant-time comparison alongside strict Origin/Referer allowlists and hardened Content-Security-Policy headers.',
        ],
      },
      {
        id: 'rbac',
        title: 'Role-Based Access Control & Tenant Isolation',
        paragraphs: [
          'Every API route and media endpoint enforces server-side organization scoping and strict least-privilege authorization across three operational roles: Administrator, Supervisor, and Care Specialist Agent.',
        ],
        bullets: [
          'Care Specialist Agents can list, inspect, play audio, and update resolution status strictly for tickets assigned to their own linked agent profile. Requests targeting any other ticket return HTTP 403 Forbidden.',
          'Supervisors govern queue operations, Human Routing Queue overrides, ticket reassignments, evaluation metrics, and read-only audit log inspection.',
          'Administrators manage agent capacity, skill assignments, confidence thresholds, retention windows, and automatic routing controls.',
          'Sliding-window rate limiting throttles login attempts (10 per 60 seconds with 5-failure account lockout), audio uploads (30 per 60 seconds), and audit exports (10 per 60 seconds).',
        ],
      },
      {
        id: 'client',
        title: 'Client & Browser Privacy',
        paragraphs: [
          'The operator web application is engineered for zero silent surveillance. No third-party behavioral analytics, session replay SDKs, advertising pixels, or external tracking beacons are bundled or loaded.',
        ],
        bullets: [
          'Authentication session identifiers are never stored in browser localStorage or sessionStorage; sessions reside strictly in HttpOnly cookies.',
          'The only optional local preference keys are non-sensitive UI settings (theme, interface language, and optionally remembered work email when explicitly checked by the operator).',
          'Browser microphone access is requested exclusively when an operator initiates a live voicemail recording, capped at 60 seconds and encoded locally to 16 kHz mono WAV before encrypted upload.',
        ],
      },
      {
        id: 'retention',
        title: 'Data Retention, Archival & Secure Erasure',
        paragraphs: [
          'Voicemail audio recordings and linked transcript/classification records are retained only for the operational period configured by the organization Administrator (90 days by default).',
          'Upon expiration of the active retention window, encrypted voicemail blobs and associated personal text fields are purged under scheduled maintenance, with purge execution recorded in the append-only Audit Log.',
        ],
      },
      {
        id: 'rights',
        title: 'Data Subject Rights & Operational Procedures',
        paragraphs: [
          'In accordance with Egyptian Law No. 151 of 2020, subscribers whose live voicemails are processed by an authorized telecom operator may exercise the following rights through the operator Data Protection Office:',
        ],
        bullets: [
          'Right to Knowledge & Access: Locate all ticket records, transcripts, and audit history linked to a verified subscriber inquiry.',
          'Right to Rectification: Correct inaccurate automated classifications or summaries via supervisor override with permanent audit provenance.',
          'Right to Erasure & Withdrawal of Consent: Purge encrypted audio recordings and anonymize personal transcript fields outside mandatory statutory compliance logs.',
          'Right to Human Intervention: Every subscriber callback is handled exclusively by a human care specialist, never an automated voice bot.',
        ],
      },
      {
        id: 'incidents',
        title: 'Security Incident & Data Breach Response',
        paragraphs: [
          'In the event of a suspected unauthorized access, credential compromise, or storage integrity anomaly, Administrators must immediately revoke active operator sessions, rotate signing and encryption keys, export the immutable Audit Log for forensic investigation, and notify the competent regulatory authority and affected individuals within statutory timelines.',
        ],
      },
      {
        id: 'contact',
        title: 'Policy Revisions & Data Protection Contact',
        paragraphs: [
          'Material updates to this Privacy Policy are versioned and published within the Platform prior to taking effect. Questions, Data Subject Requests, or compliance inquiries should be directed to your organization Administrator or Data Protection Officer at admin@telecom.local.',
        ],
      },
    ],
  },
  ar: {
    eyebrow: 'إشعار حماية البيانات والذكاء الاصطناعي السيادي',
    title: 'سياسة الخصوصية',
    subtitle:
      'توضح هذه السياسة كيف يقوم نظام SVR System (موجّه البريد الصوتي الذكي) باستقبال وتشفير وتفريغ وتصنيف وحفظ وحماية الرسائل الصوتية للمشتركين وبيانات حسابات المشغلين داخل البنية التحتية المحلية لمشغل الاتصالات.',
    docId: 'SVR-PRIVACY-2026',
    version: 'v1.0',
    effectiveDate: '26 نوفمبر 2026',
    framework: 'قانون حماية البيانات الشخصية المصري رقم 151 لسنة 2020 وضوابط الجهاز القومي لتنظيم الاتصالات',
    deployment: 'استضافة محلية أحادية المستأجر',
    highlights: [
      { label: 'النقل لجهات ذكاء اصطناعي خارجية', value: '0% تسريب خارجي' },
      { label: 'تشفير الصوت أثناء التخزين', value: 'Fernet AES-128 + HMAC' },
      { label: 'مدة الاحتفاظ الافتراضية', value: '90 يوما (قابلة للتعديل)' },
      { label: 'انتهاء الجلسة تلقائيا', value: '8 ساعات HttpOnly' },
    ],
    sections: [
      {
        id: 'scope',
        title: 'النطاق ودور المتحكم في البيانات والامتثال التنظيمي',
        paragraphs: [
          'تنطبق سياسة الخصوصية هذه على جميع عمليات معالجة الرسائل الصوتية للمشتركين، والنصوص المفرغة، وتصنيفات الفرز الذكي، وسجلات توجيه المعاودة، وحسابات المشغلين، وسجلات التدقيق التي تتم عبر منصة SVR System.',
          'تعمل مؤسسة خدمة عملاء الاتصالات المشغّلة للنظام بصفتها المتحكم في البيانات وفقا لأحكام قانون حماية البيانات الشخصية المصري رقم 151 لسنة 2020 ولوائح السرية الصادرة عن الجهاز القومي لتنظيم الاتصالات. تم تصميم المنصة كنظام دعم قرار محدود المخاطر يقوم بإعداد وتوجيه تذاكر المعاودة للموظفين المختصين فقط، ولا يتخذ أي قرارات قانونية أو مالية مؤتمتة ولا يتواصل تلقائيا مع المشتركين.',
        ],
        bullets: [
          'يعتمد التحقق والتقييم قبل الإطلاق الحقيقي حصريا على قاعدة بيانات SVR الصوتية المجمعة بموافقة موثقة وخالية من أي بيانات مشتركين فعليين.',
          'لا يُسمح بمعالجة رسائل المشتركين الحقيقيين إلا بعد استكمال مراجعة واعتماد مسؤول حماية البيانات والمستشار القانوني للمشغل.',
        ],
      },
      {
        id: 'inventory',
        title: 'حصر البيانات الشخصية وأغراض المعالجة',
        paragraphs: [
          'تقتصر المعالجة على الحد الأدنى الضروري من البيانات التشغيلية والشخصية اللازمة لتفريغ الرسائل الصوتية بالعامية المصرية والمصطلحات التقنية، وترتيب أولوية المعاودة، وتوجيه التذاكر، وحفظ سجلات الامتثال.',
        ],
        table: {
          headers: ['فئة البيانات', 'الحقول المخزنة', 'نقل خارجي للذكاء الاصطناعي', 'مدة الاحتفاظ', 'الأساس القانوني'],
          rows: [
            [
              'التسجيلات الصوتية للبريد الصوتي',
              'ملفات WAV أو MP3 أو M4A مشفرة (<= 25 ميجابايت، <= 60 ثانية) وبصمة SHA-256',
              'لا (Whisper large-v3 محلي)',
              '90 يوما افتراضيا',
              'موافقة المشترك / تقديم خدمة العملاء',
            ],
            [
              'النصوص المفرغة وبيانات التفريغ',
              'النص العربي الأصلي، النص المعياري، مزيج اللغة، ومؤشرات جودة التفريغ',
              'لا (معالجة محلية)',
              '90 يوما افتراضيا',
              'موافقة المشترك / تنفيذ الخدمة',
            ],
            [
              'سجلات التذاكر وتصنيفات الذكاء الاصطناعي',
              'نوع الشكوى، الاستعجال، حالة العميل، خطر الفقد، احتمالات التصنيف، الأولوية، والملخص',
              'لا (نماذج MARBERTv2 محلية)',
              '90 يوما افتراضيا',
              'توجيه شكاوى العملاء وإدارة الجودة',
            ],
            [
              'حسابات الموظفين والمشغلين',
              'البريد الإلكتروني، الاسم الكامل، تجزئة bcrypt، الدور، المهارات، السعة، وتجزئة الجلسة',
              'لا',
              'طوال فترة التعاقد أو التعيين',
              'علاقة العمل / التشغيل',
            ],
            [
              'سجل التدقيق غير القابل للتعديل',
              'هوية المنفذ، معرف السجل، الإجراء، القيمة القديمة والجديدة، والطابع الزمني UTC',
              'لا',
              'وفق سياسة الامتثال المؤسسية',
              'المساءلة القانونية والأمنية',
            ],
          ],
        },
      },
      {
        id: 'residency',
        title: 'حظر النقل الخارجي للذكاء الاصطناعي وتوطين البيانات',
        paragraphs: [
          'تحمل البصمة الصوتية بطبيعتها بيانات تعريفية شخصية. لذلك يقضي نظام SVR System على مخاطر الجهات الخارجية عبر تشغيل محرك التفريغ الصوتي ونماذج MARBERTv2 الأربعة بالكامل داخل شبكة الحاويات الخاصة بالمشغل.',
          'تعمل جميع الخدمات داخل شبكة معزولة على خوادم ووحدات تخزين مشفرة يسيطر عليها المشغل داخل نطاقه الجغرافي، بما يتوافق مع قيود نقل البيانات عبر الحدود في المواد 14 إلى 16 من القانون رقم 151 لسنة 2020.',
        ],
        bullets: [
          'لا يتم إرسال أي تسجيلات صوتية خام أو نصوص مفرغة أو بيانات تذاكر إلى أي واجهات ذكاء اصطناعي سحابية خارجية.',
          'لا تُستخدم تسجيلات المشتركين مطلقا في تدريب أي نماذج تجارية خارجية.',
          'أي ربط مستقبلي معتمد لنماذج نصية خارجية يظل محظورا عليه نقل الصوت الخام ويتطلب إخفاء المعرفات محليا وموافقة كتابية مسبقة.',
        ],
      },
      {
        id: 'oversight',
        title: 'الفرز الآلي والرقابة البشرية وعدم اتخاذ قرارات مؤتمتة نهائية',
        paragraphs: [
          'تُعامل جميع مخرجات التصنيف الآلي كأدوات مساعدة لقرار الموظفين المدربين وليس كقرارات نهائية مستقلة. ويتم احتساب درجة الأولوية (من 1 إلى 6) وفق معادلة حتمية شفافة.',
        ],
        bullets: [
          'بوابة الثقة: أي تنبؤ تقل ثقته عن الحد المعتمد (50% افتراضيا) أو ينقصه تصنيف يُحال تلقائيا إلى قائمة المراجعة البشرية.',
          'مراجعة وتصحيح المشرفين: يملك المشرفون صلاحية الاستماع للتسجيل المشفر وتعديل أي تصنيف مع معاينة أثر الأولوية وتسجيل مصدر التسمية (نموذج مقابل بشري).',
          'إيقاف التوجيه الآلي فورا: يمكن للمسؤول إيقاف التوزيع التلقائي في أي لحظة لإحالة جميع الرسائل الجديدة للمراجعة البشرية.',
          'أخذ عينات جودة أسبوعية: يراجع المشرفون عينة دورية من التذاكر عالية الثقة للتحقق من استقرار الدقة.',
        ],
      },
      {
        id: 'security',
        title: 'الضوابط التشفيرية والأمنية التقنية',
        paragraphs: [
          'يطبق نظام SVR System طبقات حماية متكاملة عبر التخزين والنقل والمصادقة وتصفح المشغلين.',
        ],
        bullets: [
          'التشفير أثناء التخزين: يتم تشفير كل ملف صوتي مرفوع أو مسجل باستخدام Fernet (AES-128-CBC + HMAC-SHA256) قبل كتابته على القرص، ولا يُفك التشفير إلا في الذاكرة المؤقتة أثناء التفريغ أو الاستماع المصرح به.',
          'النسخ الاحتياطي المشفر: تتضمن النسخ الاحتياطية بيان تحقق SHA-256 وتشفير Fernet كاملا مع ملف تحقق خارجي قبل الاستعادة.',
          'أمن النقل: تعتمد بيئات الإنتاج بروتوكول TLS 1.2 أو أعلى مع تفعيل HSTS وسمة Secure لملفات تعريف الارتباط.',
          'حماية كلمات المرور والجلسات: تُجزأ كلمات المرور عبر bcrypt (معامل تكلفة 12) مع حظر كلمات المرور المخترقة. وتنتهي الجلسات تلقائيا بعد 8 ساعات من الخمول وتُلغى فورا عند تسجيل الخروج أو تغيير الدور.',
          'سلامة الطلبات: تخضع جميع طلبات التعديل للتحقق المزدوج من رموز CSRF بمقارنة ثابتة الزمن مع قوائم Origin المسموح بها وترويسات CSP الصارمة.',
        ],
      },
      {
        id: 'rbac',
        title: 'التحكم في الوصول القائم على الأدوار وعزل النطاق',
        paragraphs: [
          'تتحقق الخوادم في كل طلب برمجي أو بث صوتي من معرف المؤسسة وصلاحيات الدور التشغيلي بدقة عبر ثلاثة أدوار: المسؤول، والمشرف، وموظف خدمة العملاء.',
        ],
        bullets: [
          'يقتصر وصول موظف خدمة العملاء على عرض وتشغيل وتحديث التذاكر المسندة إليه شخصيا فقط، وتُرفض أي محاولة للوصول إلى تذاكر أخرى برمز HTTP 403.',
          'يدير المشرفون طوابير العمل، وتصحيحات قائمة المراجعة البشرية، وإعادة الإسناد، ومؤشرات الأداء، وسجل التدقيق للقراءة فقط.',
          'يدير المسؤولون سعة الموظفين والمهارات وحدود الثقة وسياسات الاحتفاظ وإعدادات التوجيه الآلي.',
          'تحد حدود المعدل الزمنية من محاولات تسجيل الدخول (10 محاولات كل 60 ثانية مع قفل مؤقت بعد 5 إخفاقات) ومن رفع الملفات وتصدير السجلات.',
        ],
      },
      {
        id: 'client',
        title: 'خصوصية المتصفح وعدم التتبع الصامت',
        paragraphs: [
          'تم بناء واجهة المشغلين دون أي أدوات تتبع سلوكي أو حزم إعادة تشغيل الجلسات أو إعلانات أو منارات مراقبة خارجية.',
        ],
        bullets: [
          'لا تُخزن رموز الجلسة أو المصادقة إطلاقا في localStorage أو sessionStorage، بل تُحفظ حصرا في ملفات HttpOnly الآمنة.',
          'تقتصر التفضيلات المحلية الاختيارية على إعدادات الواجهة غير الحساسة كالسمة واللغة أو تذكّر بريد العمل عند اختياره صراحة.',
          'لا يُطلب الوصول إلى الميكروفون إلا عند بدء المشغل لتسجيل رسالة صوتية يدويا وبحد أقصى 60 ثانية.',
        ],
      },
      {
        id: 'retention',
        title: 'الاحتفاظ بالبيانات والحذف الآمن',
        paragraphs: [
          'تُحفظ التسجيلات الصوتية والنصوص والتصنيفات المرتبطة بها للمدة التشغيلية المعتمدة من المسؤول (90 يوما افتراضيا).',
          'عند انقضاء مدة الاحتفاظ، تُحذف الملفات الصوتية المشفرة والبيانات النصية الشخصية المجدولة بشكل آمن مع توثيق عملية الحذف في سجل التدقيق.',
        ],
      },
      {
        id: 'rights',
        title: 'حقوق أصحاب البيانات وإجراءات التنفيذ',
        paragraphs: [
          'وفقا لقانون حماية البيانات الشخصية المصري رقم 151 لسنة 2020، يتمتع المشتركون بالحقوق التالية عبر مكتب حماية البيانات لدى المشغل:',
        ],
        bullets: [
          'حق العلم والوصول: تحديد جميع التذاكر والنصوص وسجلات التدقيق المرتبطة بطلب المشترك بعد التحقق من هويته.',
          'حق التصحيح: تعديل أي تصنيف أو ملخص غير دقيق عبر صلاحية المشرف مع حفظ سجل التغيير الكامل.',
          'حق المحو وسحب الموافقة: حذف الملفات الصوتية المشفرة وإخفاء الهوية من النصوص خارج السجلات الإلزامية القانونية.',
          'حق التدخل البشري: تُجرى جميع مكالمات المعاودة بواسطة موظفين بشريين مؤهلين وليس عبر أنظمة اتصال آلية.',
        ],
      },
      {
        id: 'incidents',
        title: 'الاستجابة للحوادث الأمنية واختراق البيانات',
        paragraphs: [
          'عند الاشتباه في أي وصول غير مصرح به أو تسريب بيانات، يلتزم المسؤولون بإلغاء جميع الجلسات النشطة فورا، وتدوير مفاتيح التشفير والتوقيع، وتصدير سجل التدقيق للتحقيق الجنائي الرقمي، وإخطار الجهات المختصة والأفراد المتأثرين وفق المهلة القانونية.',
        ],
      },
      {
        id: 'contact',
        title: 'تحديثات السياسة والتواصل',
        paragraphs: [
          'تُوثق أي تحديثات جوهرية لهذه السياسة برقم إصدار وتاريخ سريان واضح داخل المنصة قبل تطبيقها. للاستفسارات أو طلبات حقوق البيانات يرجى التواصل مع مسؤول النظام أو مسؤول حماية البيانات عبر admin@telecom.local.',
        ],
      },
    ],
  },
}

export const TERMS_DOC: Record<'en' | 'ar', LegalDoc> = {
  en: {
    eyebrow: 'Enterprise Operator Governance & Acceptable Use',
    title: 'Terms of Use',
    subtitle:
      'Establishes the binding operational, confidentiality, access-control, and human-oversight obligations governing all authorized administrators, supervisors, and care specialists using SVR System.',
    docId: 'SVR-TERMS-2026',
    version: 'v1.0',
    effectiveDate: '26 Nov 2026',
    framework: 'Arab Republic of Egypt Laws & NTRA Operational Standards',
    deployment: 'Authorized Personnel Only',
    highlights: [
      { label: 'Access Scope', value: 'Authorized Staff Only' },
      { label: 'Audit Logging', value: '100% Immutable Trail' },
      { label: 'Human Accountability', value: 'Mandatory Script Review' },
      { label: 'Audio Handling', value: 'No Unapproved Export' },
    ],
    sections: [
      {
        id: 'acceptance',
        title: 'Acceptance, Binding Scope & Authorized Personnel',
        paragraphs: [
          'By signing into SVR System ("the Platform"), you acknowledge that you are an authorized employee, contractor, or care specialist of the operating telecom organization and agree to comply strictly with these Terms of Use, applicable internal security policies, and Egyptian telecom regulations.',
          'Unauthorized access, automated scraping, or attempted probing by unauthenticated parties is strictly prohibited and may result in immediate account revocation and legal action.',
        ],
      },
      {
        id: 'accounts',
        title: 'Account Provisioning, Credentials & Session Security',
        paragraphs: [
          'Operator accounts are provisioned and managed exclusively by designated system Administrators. Self-registration is disabled across the Platform.',
        ],
        bullets: [
          'Credential Non-Sharing: You must never share your work email, password, or active browser session with colleagues or third parties.',
          'Password Hygiene: Passwords must meet complexity standards (minimum 10 characters with mixed case and digits) and must not reuse breached or organizational default credentials.',
          'Automatic Locking & Timeout: Sessions expire automatically after 8 hours of inactivity. You must explicitly sign out before leaving an unattended workstation.',
          'Immediate Revocation: Access privileges terminate immediately upon role transfer, suspension, or separation from the organization.',
        ],
      },
      {
        id: 'roles',
        title: 'Role Permissions & Least-Privilege Matrix',
        paragraphs: [
          'Operational authority inside SVR System is enforced server-side according to the least-privilege boundaries summarized below. Operators may not attempt to circumvent or escalate beyond their assigned role.',
        ],
        table: {
          headers: ['Role', 'Permitted Operational Actions', 'Enforced Restrictions'],
          rows: [
            [
              'Care Specialist (Agent)',
              'View assigned tickets, stream authorized encrypted audio, use grounded callback brief, mark in-progress or resolved',
              'Cannot view unassigned or peer tickets (HTTP 403), override AI labels, export audit logs, or alter settings',
            ],
            [
              'Care Supervisor',
              'Manage full queue, process Human Routing Queue, preview & override AI labels, reassign tickets, review model metrics, export audit logs',
              'Cannot alter system-wide retention, confidence thresholds, or global automatic routing controls',
            ],
            [
              'System Administrator',
              'All supervisor operations plus agent shift/capacity management, confidence thresholds, retention days, and automatic routing pause',
              'All administrative modifications are permanently logged with before/after JSON diffs',
            ],
          ],
        },
      },
      {
        id: 'acceptable-use',
        title: 'Acceptable Use & Prohibited Conduct',
        paragraphs: [
          'Operators must use the Platform solely for legitimate subscriber complaint triage, callback preparation, quality assurance, and capacity management.',
        ],
        bullets: [
          'You shall not download, screen-record, capture via external devices, or redistribute subscriber voicemail audio or transcripts outside authorized Platform playback.',
          'You shall not copy, paste, or transmit subscriber transcripts, phone numbers, or case details into unauthorized external chatbots, public LLMs, or personal messaging apps.',
          'You shall not attempt to bypass rate limits, CSRF protections, confidence gates, or role-based access boundaries.',
          'You shall not submit test, malformed, abusive, or non-operational audio files into production queues.',
        ],
      },
      {
        id: 'confidentiality',
        title: 'Confidentiality & Telecom Secrecy Obligations',
        paragraphs: [
          'All subscriber voicemails, voice recordings, billing disputes, network complaints, emotional assessments, and churn-risk indicators constitute confidential telecom customer communications protected under Egyptian telecommunications secrecy laws and Law No. 151 of 2020.',
          'Confidentiality obligations survive the termination of an operator session, reassignment, or employment.',
        ],
      },
      {
        id: 'ai-boundaries',
        title: 'AI Decision-Support Boundaries & Human Accountability',
        paragraphs: [
          'Automated transcripts, classifications, priority scores, and suggested Arabic/English opening scripts are provided exclusively to accelerate human operator preparation.',
        ],
        bullets: [
          'Human Verification: Operators must verify subscriber identity and confirm complaint context during the live callback rather than treating AI summaries as infallible.',
          'Grounded Scripts Only: Suggested scripts are deterministically assembled from verified ticket attributes and approved templates; operators remain accountable for professional communication on the call.',
          'Zero Autonomous Outreach: The Platform never places automated calls or sends unreviewed messages to subscribers.',
        ],
      },
      {
        id: 'overrides',
        title: 'Supervisor Overrides, Provenance & Routing Controls',
        paragraphs: [
          'Supervisors reviewing items in the Human Routing Queue or auditing live tickets must inspect the transcript and encrypted audio before applying label corrections. Every correction displays a priority and skill-routing impact preview prior to confirmation.',
          'Confirmed overrides preserve original model predictions alongside human provenance and cannot be silently erased. Administrators may engage the global automatic routing pause whenever operational anomalies or model-drift alerts require manual triage.',
        ],
      },
      {
        id: 'audit',
        title: 'Mandatory Audit Logging & Compliance Monitoring',
        paragraphs: [
          'Every authentication event, voicemail upload, AI classification run, audio playback request, label override, ticket reassignment, status transition, setting modification, and audit export is permanently recorded in the append-only Audit Log with actor identity and UTC timestamp.',
          'Operators acknowledge and consent to continuous security and quality auditing of all Platform activity.',
        ],
      },
      {
        id: 'intake',
        title: 'Voicemail Intake & Audio Submission Standards',
        paragraphs: [
          'Voicemails submitted via file upload or live browser recording must conform to validated technical constraints: WAV, MP3, or M4A format, maximum 25 MB file size, and maximum 60 seconds duration (15 to 60 seconds recommended for optimal transcription and classification accuracy).',
          'Duplicate submissions are detected via SHA-256 content digests and idempotency keys to preserve queue integrity.',
        ],
      },
      {
        id: 'continuity',
        title: 'Service Availability, Backups & Operational Continuity',
        paragraphs: [
          'SVR System is operated on self-hosted infrastructure managed by the organization. Regular encrypted backups and SHA-256 restore drills protect ticket and audit continuity. During scheduled maintenance or elevated pipeline latency, supervisors may transition queues to manual handling via Routing Settings.',
        ],
      },
      {
        id: 'enforcement',
        title: 'Enforcement, Suspension & Disciplinary Remedies',
        paragraphs: [
          'Violations of these Terms of Use, including unauthorized audio extraction, credential sharing, or external disclosure of subscriber data, may result in immediate session termination, permanent account suspension, internal disciplinary action, and civil or criminal referral under applicable law.',
        ],
      },
      {
        id: 'governing-law',
        title: 'Governing Law, Amendments & Compliance Contact',
        paragraphs: [
          'These Terms of Use are governed by the laws of the Arab Republic of Egypt and applicable NTRA regulatory directives. The operating organization may update these Terms from time to time; continued use of the Platform after publication constitutes acceptance of the revised Terms.',
          'For access requests, incident reporting, or compliance questions, contact your system Administrator at admin@telecom.local.',
        ],
      },
    ],
  },
  ar: {
    eyebrow: 'حوكمة المشغلين والاستخدام المقبول للمؤسسة',
    title: 'شروط الاستخدام',
    subtitle:
      'تحدد هذه الشروط الالتزامات الملزمة المتعلقة بالتشغيل والسرية والتحكم في الوصول والرقابة البشرية لجميع المسؤولين والمشرفين وموظفي خدمة العملاء المصرح لهم باستخدام نظام SVR System.',
    docId: 'SVR-TERMS-2026',
    version: 'v1.0',
    effectiveDate: '26 نوفمبر 2026',
    framework: 'قوانين جمهورية مصر العربية ولوائح الجهاز القومي لتنظيم الاتصالات',
    deployment: 'للموظفين المصرح لهم فقط',
    highlights: [
      { label: 'نطاق الوصول', value: 'الموظفون المصرح لهم فقط' },
      { label: 'سجل التدقيق', value: 'توثيق دائم 100%' },
      { label: 'المسؤولية البشرية', value: 'مراجعة إلزامية قبل الاتصال' },
      { label: 'حماية الصوت', value: 'يُحظر التصدير غير المصرح' },
    ],
    sections: [
      {
        id: 'acceptance',
        title: 'القبول والنطاق الملزم والمستخدمون المصرح لهم',
        paragraphs: [
          'بتسجيل دخولك إلى منصة SVR System، فإنك تقر بأنك موظف أو متعاقد أو أخصائي خدمة عملاء مصرح له من قبل مؤسسة الاتصالات المشغّلة، وتوافق على الالتزام الكامل بشروط الاستخدام هذه والسياسات الأمنية الداخلية ولوائح الاتصالات المصرية.',
          'يُحظر تماما أي دخول غير مصرح به أو استخراج آلي للبيانات أو محاولة فحص أمني غير مأذون بها، ويعرض مرتكبه لإلغاء الوصول فورا والمساءلة القانونية.',
        ],
      },
      {
        id: 'accounts',
        title: 'إدارة الحسابات وبيانات الاعتماد وأمن الجلسات',
        paragraphs: [
          'تُنشأ حسابات المشغلين وتُدار حصريا بواسطة مسؤولي النظام المعتمدين، ولا يتاح التسجيل الذاتي عبر المنصة.',
        ],
        bullets: [
          'حظر مشاركة بيانات الدخول: يُمنع منعا باتا مشاركة بريد العمل أو كلمة المرور أو جلسة المتصفح النشطة مع أي زميل أو طرف ثالث.',
          'جودة كلمة المرور: يجب أن تستوفي كلمات المرور متطلبات التعقيد (10 أحرف على الأقل تشمل حروفا وأرقاما) دون إعادة استخدام كلمات مرور مخترقة.',
          'القفل وانتهاء المهلة: تنتهي الجلسات تلقائيا بعد 8 ساعات من عدم النشاط، ويجب تسجيل الخروج يدويا قبل مغادرة جهاز العمل.',
          'الإلغاء الفوري: تُسحب الصلاحيات فورا عند تغيير الدور الوظيفي أو الإيقاف أو انتهاء الخدمة.',
        ],
      },
      {
        id: 'roles',
        title: 'مصفوفة الأدوار والحد الأدنى من الصلاحيات',
        paragraphs: [
          'تُطبق الصلاحيات داخل النظام على مستوى الخادم وفق مبدأ الحد الأدنى من الامتيازات كما هو موضح أدناه، ويُحظر محاولة تجاوز حدود الدور المعين.',
        ],
        table: {
          headers: ['الدور الوظيفي', 'الإجراءات التشغيلية المسموحة', 'القيود المفروضة'],
          rows: [
            [
              'موظف خدمة العملاء',
              'عرض التذاكر المسندة إليه، تشغيل التسجيل الصوتي المصرح به، استخدام ملخص المعاودة، وتحديث حالة التنفيذ والإغلاق',
              'ممنوع من عرض تذاكر غير مسندة أو تذاكر الزملاء (HTTP 403) أو تعديل التصنيفات أو تصدير سجل التدقيق',
            ],
            [
              'مشرف خدمة العملاء',
              'إدارة الطابور الكامل، معالجة قائمة المراجعة البشرية، معاينة وتصحيح التصنيفات، إعادة الإسناد، ومراقبة أداء النماذج وسجل التدقيق',
              'لا يملك تعديل إعدادات الاحتفاظ بالبيانات أو حدود الثقة أو إيقاف التوجيه الآلي العام',
            ],
            [
              'مسؤول النظام',
              'جميع صلاحيات المشرف بالإضافة إلى إدارة سعة ومهارات الموظفين، وحدود الثقة، ومدة الاحتفاظ، وإيقاف التوجيه الآلي',
              'تُسجل جميع التعديلات الإدارية بشكل دائم مع القيم السابقة والجديدة',
            ],
          ],
        },
      },
      {
        id: 'acceptable-use',
        title: 'الاستخدام المقبول والسلوكيات المحظورة',
        paragraphs: [
          'يلتزم المشغلون باستخدام المنصة حصرا لأغراض فرز شكاوى المشتركين، وإعداد مكالمات المعاودة، وضمان الجودة، وإدارة السعة.',
        ],
        bullets: [
          'يُحظر تنزيل أو تسجيل الشاشة أو التقاط الصوت بأجهزة خارجية أو إعادة توزيع التسجيلات والنصوص خارج التشغيل المصرح به داخل المنصة.',
          'يُحظر نسخ أو لصق نصوص المشتركين أو أرقامهم أو تفاصيل شكاواهم في أي أدوات ذكاء اصطناعي خارجية أو تطبيقات مراسلة شخصية.',
          'يُحظر محاولة تجاوز حدود المعدل الزمنية أو حماية CSRF أو بوابات الثقة أو قيود الصلاحيات.',
          'يُحظر رفع ملفات صوتية غير صالحة أو مسيئة أو غير تشغيلية إلى طوابير الإنتاج.',
        ],
      },
      {
        id: 'confidentiality',
        title: 'التزامات السرية وسرية اتصالات المشتركين',
        paragraphs: [
          'تُعد جميع الرسائل الصوتية للمشتركين والتفريغات النصية وتفاصيل الفواتير والشبكة ومؤشرات الحالة الشعورية وخطر الفقد مراسلات اتصالات سرية محمية بموجب قوانين سرية الاتصالات المصرية والقانون رقم 151 لسنة 2020.',
          'تستمر التزامات السرية حتى بعد انتهاء الجلسة أو تغيير القسم أو انتهاء علاقة العمل.',
        ],
      },
      {
        id: 'ai-boundaries',
        title: 'حدود دعم القرار بالذكاء الاصطناعي والمسؤولية البشرية',
        paragraphs: [
          'تُقدم النصوص المفرغة والتصنيفات ودرجات الأولوية ونصوص الافتتاح المقترحة كوسائل مساعدة لتسريع تحضير الموظف فقط.',
        ],
        bullets: [
          'التحقق البشري: يجب على الموظف التحقق من هوية المشترك وسياق الشكوى أثناء المكالمة الفعلية وعدم الاعتماد الأعمى على الملخص الآلي.',
          'النصوص المعتمدة: تُبنى النصوص المقترحة من بيانات التذكرة الموثقة والقوالب المعتمدة، ويظل الموظف مسؤولا عن جودة التواصل المهني أثناء المكالمة.',
          'عدم التواصل الآلي: لا تجري المنصة أي مكالمات آلية ولا ترسل رسائل غير مراجعة للمشتركين.',
        ],
      },
      {
        id: 'overrides',
        title: 'تصحيحات المشرفين ومصدر التسمية وضوابط التوجيه',
        paragraphs: [
          'يجب على المشرفين عند مراجعة قائمة المراجعة البشرية فحص النص المفرغ والاستماع للتسجيل المشفر قبل اعتماد أي تصحيح، مع مراجعة معاينة أثر الأولوية والمهارة قبل الحفظ.',
          'تحفظ التصحيحات المعتمدة التصنيف الأصلي للنموذج جنبا إلى جنب مع مصدر التعديل البشري ولا يمكن محوها. ويحق للمسؤول تفعيل الإيقاف الفوري للتوجيه الآلي عند الحاجة التشغيلية.',
        ],
      },
      {
        id: 'audit',
        title: 'التوثيق الإلزامي ومراقبة الامتثال',
        paragraphs: [
          'يُسجل كل تسجيل دخول، ورفع أو تسجيل صوتي، وتشغيل تصنيف، وطلب استماع، وتصحيح تصنيف، وإعادة إسناد، وتغيير حالة، وتعديل إعدادات، وتصدير سجل بشكل دائم في سجل التدقيق غير القابل للتعديل.',
          'يقر المشغلون بخضوع جميع الأنشطة على المنصة للمراجعة الأمنية والجودة المستمرة.',
        ],
      },
      {
        id: 'intake',
        title: 'معايير استقبال ورفع الملفات الصوتية',
        paragraphs: [
          'يجب أن تلتزم الرسائل الصوتية المرفوعة أو المسجلة عبر المتصفح بالصيغ المعتمدة (WAV أو MP3 أو M4A) وبحد أقصى 25 ميجابايت و60 ثانية للمدة (ويوصى بمدة 15 إلى 60 ثانية لأعلى دقة تفريغ وتصنيف).',
          'يتم اكتشاف التكرار عبر بصمة SHA-256 ومفاتيح عدم التكرار لحماية سلامة الطابور.',
        ],
      },
      {
        id: 'continuity',
        title: 'توافر الخدمة والنسخ الاحتياطي واستمرارية التشغيل',
        paragraphs: [
          'تُشغل منصة SVR System على بنية تحتية محلية تديرها المؤسسة، وتُجرى نسخ احتياطية مشفرة واختبارات استعادة دورية لحماية استمرارية التذاكر وسجلات التدقيق.',
        ],
      },
      {
        id: 'enforcement',
        title: 'الإنفاذ والإيقاف والإجراءات التأديبية',
        paragraphs: [
          'قد يؤدي أي إخلال بشروط الاستخدام هذه، بما في ذلك استخراج الصوت دون إذن أو مشاركة بيانات الاعتماد أو إفشاء بيانات المشتركين، إلى إنهاء الجلسة فورا، وإيقاف الحساب نهائيا، والمساءلة التأديبية والقانونية.',
        ],
      },
      {
        id: 'governing-law',
        title: 'القانون الواجب التطبيق والتعديلات والتواصل',
        paragraphs: [
          'تخضع شروط الاستخدام هذه لقوانين جمهورية مصر العربية ولوائح الجهاز القومي لتنظيم الاتصالات. ويجوز للمؤسسة تحديث هذه الشروط عند اللزوم، ويعد استمرار الاستخدام بعد النشر قبولا للشروط المحدثة.',
          'لطلبات الصلاحيات أو الإبلاغ عن الحوادث أو استفسارات الامتثال، يرجى التواصل مع مسؤول النظام عبر admin@telecom.local.',
        ],
      },
    ],
  },
}
