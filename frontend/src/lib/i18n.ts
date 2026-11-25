/* Bilingual EN / Egyptian Arabic telecom care dictionary with Unicode bidi isolates */

export type Locale = "en" | "ar";

/** Wrap an LTR technical term for clean inline rendering inside Arabic RTL lines. */
export function bidi(term: string): string {
  return `\u2066${term}\u2069`;
}

export const CATEGORY_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    network_and_connectivity: "Network & Connectivity",
    billing_and_charges: "Billing & Charges",
    balance_and_data: "Balance & Data Bundles",
    app_and_account: "Subscriber App & Account",
    branch_and_staff: "Branch & Care Staff",
    no_reply_or_long_wait: "Delayed Follow-up & Wait Time",
    cancellation_request: "Line Cancellation & Retention",
    thanks_or_praise: "Appreciation & Positive Feedback",
    other: "General Subscriber Inquiry",
    offers_and_packages: "Rate Plans & Offers",
    sim_services: "SIM & eSIM Services",
  },
  ar: {
    network_and_connectivity: "الشبكة والتغطية",
    billing_and_charges: "الفواتير والرسوم",
    balance_and_data: "الرصيد وباقات الإنترنت",
    app_and_account: "التطبيق وحساب المشترك",
    branch_and_staff: "الفروع وخدمة العملاء",
    no_reply_or_long_wait: "تأخر الرد والمتابعة",
    cancellation_request: "طلب إلغاء الخط",
    thanks_or_praise: "شكر وإشادة بالخدمة",
    other: "استفسار عام",
    offers_and_packages: "العروض والباقات",
    sim_services: `خدمات الشريحة و ${bidi("eSIM")}`,
  },
};

export const URGENCY_LABELS: Record<Locale, Record<string, string>> = {
  en: { high: "High", medium: "Medium", low: "Low" },
  ar: { high: "عاجل", medium: "متوسط", low: "منخفض" },
};

export const STATE_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    calm: "Calm",
    frustrated: "Frustrated",
    mad: "Mad",
    satisfied: "Satisfied",
    unclear: "Unclear",
  },
  ar: {
    calm: "هادئ",
    frustrated: "محبط",
    mad: "غاضب",
    satisfied: "راضٍ",
    unclear: "غير واضح",
  },
};

export const CHURN_LABELS: Record<Locale, Record<string, string>> = {
  en: { at_risk: "At Risk", not_at_risk: "Not At Risk" },
  ar: { at_risk: "معرض لإلغاء الخط", not_at_risk: "غير معرض للإلغاء" },
};

export const BUCKET_LABELS: Record<Locale, Record<string, string>> = {
  en: { urgent: "Urgent", high: "High", normal: "Normal", low: "Low" },
  ar: { urgent: "عاجل جدا", high: "مرتفع", normal: "عادي", low: "منخفض" },
};

export const STATUS_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    received: "Received",
    processing: "Processing",
    ready: "Ready",
    unassigned: "Unassigned",
    in_progress: "In Progress",
    resolved: "Resolved",
    closed: "Closed",
    failed: "Failed",
  },
  ar: {
    received: "تم الاستلام",
    processing: "قيد المعالجة",
    ready: "جاهز للمعاودة",
    unassigned: "غير معين",
    in_progress: "جاري المتابعة",
    resolved: "تم الحل",
    closed: "مغلق",
    failed: "فشل المعالجة",
  },
};

export const SKILL_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    Network: "Network Care",
    Billing: "Billing & Bundles Care",
    General: "Subscriber & Retention Care",
  },
  ar: {
    Network: "فريق رعاية الشبكة",
    Billing: "فريق الفواتير والباقات",
    General: "فريق رعاية المشتركين والاستبقاء",
  },
};

export const REVIEW_REASON_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    low_confidence: "Low Confidence",
    missing_label: "Missing Label",
    invalid_label: "Invalid Label",
    no_eligible_agent: "No Eligible Agent",
    processing_error: "Processing Error",
    kill_switch_active: "Automatic Routing Paused",
    supervisor_requested: "Supervisor Requested Review",
    weekly_quality_sample: "Weekly 5% Quality Sample",
  },
  ar: {
    low_confidence: "ثقة النموذج منخفضة",
    missing_label: "تصنيف ناقص",
    invalid_label: "تصنيف خارج القائمة المعتمدة",
    no_eligible_agent: "لا يوجد موظف متاح بالسعة المطلوبة",
    processing_error: "خطأ في خط المعالجة",
    kill_switch_active: "التوجيه التلقائي متوقف",
    supervisor_requested: "مراجعة مطلوبة من المشرف",
    weekly_quality_sample: "عينة الجودة الأسبوعية 5%",
  },
};

export const FIELD_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    complaint_category: "Complaint Category",
    complaint_urgency: "Complaint Urgency",
    customer_state: "Customer State",
    churn_risk: "Churn Risk",
  },
  ar: {
    complaint_category: "فئة الشكوى",
    complaint_urgency: "درجة الاستعجال",
    customer_state: "حالة المشترك",
    churn_risk: "خطر فقدان المشترك",
  },
};

export const LANGUAGE_MIX_LABELS: Record<Locale, Record<string, string>> = {
  en: {
    arabic_only: "Egyptian Arabic",
    arabic_with_english_telecom_terms: "Arabic + English Telecom Terms",
    mixed: "Mixed Arabic / English",
  },
  ar: {
    arabic_only: "عربي مصري",
    arabic_with_english_telecom_terms: "عربي مع مصطلحات اتصالات إنجليزية",
    mixed: "مختلط عربي وإنجليزي",
  },
};

export const UI_COPY = {
  en: {
    appName: "SVR System",
    orgName: "Egypt Telecom Care",
    skipToMain: "Skip to main content",
    navQueue: "Callback Queue",
    navMyTickets: "My Callbacks",
    navReviewQueue: "Human Routing Queue",
    navEvaluation: "Model Evaluation",
    navAuditLog: "Audit Log",
    navAgents: "Agents & Skills",
    navSettings: "Routing Settings",
    navSectionOps: "Operations",
    navSectionAdmin: "Administration",
    wsConnected: "Live queue connected",
    wsReconnecting: "Reconnecting queue",
    wsOffline: "Live updates offline",
    killSwitchBanner:
      "Automatic routing is paused. All new subscriber voicemails are routed to the Human Routing Queue.",
    manageKillSwitch: "Manage in Settings",
    themeLight: "Light",
    themeDark: "Dark",
    signOut: "Sign out",
    privacy: "Privacy",
    terms: "Terms",
    intakeOpen: "New Voicemail",
    intakeTitle: "Subscriber Voicemail Intake",
    intakeSub: "Upload a recorded voicemail or record in-browser for immediate pipeline classification.",
    intakeTabUpload: "Upload File",
    intakeTabRecord: "Record Audio",
    intakeSpec: "Accepted: WAV, MP3, or M4A up to 25 MB and 60 seconds. 15 to 60 seconds recommended for optimal accuracy.",
    intakeSubmit: "Submit Voicemail",
    intakeSubmitting: "Submitting...",
    allBuckets: "All",
    searchPlaceholder: "Search Arabic or English transcript...",
    filterCategory: "Category",
    filterStatus: "Status",
    filterAgent: "Assigned Agent",
    filterReason: "Review Reason",
    allOption: "All",
    unassignedOption: "Unassigned",
    previous: "Previous",
    next: "Next",
    loading: "Loading operations data...",
    noTickets: "No subscriber tickets match the current filters.",
    modelOutput: "Model output · MARBERTv2",
    humanCorrection: "Human correction",
    neverSentAuto: "Callback script is prepared for operator voice callback only. Never sent automatically to the subscriber.",
    copyScript: "Copy Script",
    copied: "Copied",
    previewCorrection: "Preview Recomputed Route",
    confirmCorrection: "Confirm Correction",
    cancel: "Cancel",
    confirm: "Confirm",
    saveChanges: "Save Changes",
    backToQueue: "Back to Queue",
  },
  ar: {
    appName: `عمليات ${bidi("SVR")}`,
    orgName: "رعاية عملاء الاتصالات - مصر",
    skipToMain: "تخطي إلى المحتوى الرئيسي",
    navQueue: "قائمة معاودة الاتصال",
    navMyTickets: "تذاكري المخصصة",
    navReviewQueue: "قائمة المراجعة والتوجيه البشري",
    navEvaluation: "تقييم النماذج والجودة",
    navAuditLog: "سجل التدقيق",
    navAgents: "الموظفون والمهارات",
    navSettings: "إعدادات التوجيه",
    navSectionOps: "التشغيل اليومي",
    navSectionAdmin: "إدارة النظام",
    wsConnected: "التحديث المباشر متصل",
    wsReconnecting: "إعادة توصيل التحديث المباشر",
    wsOffline: "التحديث المباشر غير متصل",
    killSwitchBanner:
      "التوجيه التلقائي متوقف مؤقتا. يتم تحويل كل الرسائل الصوتية الجديدة إلى قائمة المراجعة والتوجيه البشري.",
    manageKillSwitch: "إدارة من الإعدادات",
    themeLight: "فاتح",
    themeDark: "داكن",
    signOut: "تسجيل الخروج",
    privacy: "الخصوصية",
    terms: "الشروط",
    intakeOpen: "رسالة صوتية جديدة",
    intakeTitle: "استلام رسالة صوتية لمشترك",
    intakeSub: "ارفع ملف صوتي أو سجل من الميكروفون لمعالجة الشكوى وتوجيهها فورا.",
    intakeTabUpload: "رفع ملف",
    intakeTabRecord: "تسجيل صوتي",
    intakeSpec: `الصيغ المقبولة: ${bidi("WAV / MP3 / M4A")} حتى ${bidi("25 MB")} و ${bidi("60")} ثانية. يفضل من 15 إلى 60 ثانية لأفضل دقة.`,
    intakeSubmit: "إرسال الرسالة الصوتية",
    intakeSubmitting: "جاري الإرسال...",
    allBuckets: "الكل",
    searchPlaceholder: "ابحث في النص الصوتي بالعربية أو الإنجليزية...",
    filterCategory: "الفئة",
    filterStatus: "الحالة",
    filterAgent: "الموظف المعين",
    filterReason: "سبب المراجعة",
    allOption: "الكل",
    unassignedOption: "غير معين",
    previous: "السابق",
    next: "التالي",
    loading: "جاري تحميل البيانات...",
    noTickets: "لا توجد تذاكر مطابقة لخيارات التصفية الحالية.",
    modelOutput: `مخرجات النموذج · ${bidi("MARBERTv2")}`,
    humanCorrection: "تصحيح بشري",
    neverSentAuto: "نص معاودة الاتصال للاستخدام الصوتي من الموظف فقط، ولا يرسل تلقائيا للمشترك أبدا.",
    copyScript: "نسخ النص",
    copied: "تم النسخ",
    previewCorrection: "معاينة الأولوية والتوجيه الجديد",
    confirmCorrection: "تأكيد التصحيح",
    cancel: "إلغاء",
    confirm: "تأكيد",
    saveChanges: "حفظ التغييرات",
    backToQueue: "العودة للقائمة",
  },
} as const;

export function labelForCategory(cat: string | null | undefined, locale: Locale): string {
  if (!cat) return "-";
  return CATEGORY_LABELS[locale][cat] || cat;
}

export function labelForUrgency(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return URGENCY_LABELS[locale][val] || val;
}

export function labelForState(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return STATE_LABELS[locale][val] || val;
}

export function labelForChurn(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return CHURN_LABELS[locale][val] || val;
}

export function labelForBucket(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return BUCKET_LABELS[locale][val] || val;
}

export function labelForStatus(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return STATUS_LABELS[locale][val] || val;
}

export function labelForSkill(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return SKILL_LABELS[locale][val] || val;
}

export function labelForReviewReason(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return REVIEW_REASON_LABELS[locale][val] || val;
}

export function labelForLanguageMix(val: string | null | undefined, locale: Locale): string {
  if (!val) return "-";
  return LANGUAGE_MIX_LABELS[locale][val] || val;
}
