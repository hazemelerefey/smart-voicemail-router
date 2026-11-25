# Smart Voicemail Router (SVR) - Data Protection Impact Assessment (DPIA)

**Document ID:** SVR-DPIA-01  
**PRD Reference:** `docs/project/PRD.md` (`SVR-PRD-02` v1.0, Sections 9, 10.1-10.5, 11.4, 21)  
**Regulatory Alignment:** Egyptian Personal Data Protection Law (Law No. 151 of 2020) and Limited-Risk AI Oversight Principles  
**Status:** Pre-Launch Assessment (pending operator legal counsel sign-off per Open Question Q6)  
**Last Updated:** 2026-11-24  
**Owner:** SVR Team  

---

## 1. Executive Summary and Processing Purpose

Smart Voicemail Router (SVR) is a single-tenant, local-first web application operated by a telecom customer-care organization. It transcribes single-speaker Egyptian Arabic subscriber voicemails (up to 60 seconds), classifies four operational attributes (`complaint_category`, `complaint_urgency`, `customer_state`, `churn_risk`), computes an explainable queue priority, and routes callback tickets to available customer-care agents.

- **AI Risk Tier:** Limited-risk decision-support system. SVR prepares and routes internal callback tickets; it never makes automated decisions with legal or financial effect, never contacts subscribers automatically, and operates under continuous human oversight (supervisor corrections, Human Review Queue, and immediate automatic routing kill switch).
- **Initial Deployment Corpus:** The initial deployment and validation rely strictly on the simulated **SVR Voicemail Corpus** (5,096 clean rows recorded by contributors with documented consent; acted emotions; zero real subscriber PII). Real subscriber voicemails may only be ingested after the telecom operator's legal advisor completes regulatory review and sign-off (PRD A6, Q6).

---

## 2. Personal Data Inventory and Legal Basis

Aligned with PRD Section 10.2 and Egyptian Law No. 151 of 2020 (Articles 2, 3, and 6 on lawful basis, purpose limitation, and storage limitation):

| Data Category | Concrete Fields Stored | Sent to Third-Party AI? | Retention Period | Redaction / Protection | Legal Basis |
|---|---|---|---|---|---|
| Voicemail audio recordings | Encrypted WAV, MP3, or M4A bytes (`<= 25 MB`, `<= 60 s`), duration, SHA-256 digest | **No** (self-hosted local Whisper `large-v3` only) | Configurable via `SystemSetting.retention_days`, default **90 days** (Q1) | Fernet authenticated encryption at rest (`AES-128-CBC + HMAC-SHA256`); voice inherently identifies speaker so raw audio stays local | Contributor consent for simulated corpus; explicit subscriber consent / customer-care contract once approved for live telecom operations |
| Transcripts and STT metadata | `transcript`, `text_norm`, 10-column STT v1 JSON (`min_avg_logprob`, `max_no_speech_prob`, etc.) | **No** (processed locally by default) | Same as parent ticket (default **90 days**) | Direct identifiers (phone numbers, national IDs, names) must be masked locally before any future approved external text call | Consent / legitimate telecom service handling |
| Ticket records and AI logs | 4 labels, class probabilities, `label_sources`, confidence, priority, `route_reason`, callback brief, `AIInteractionLog` | **No** | Same as parent ticket (default **90 days**) | Strict single-tenant `organization_id` isolation; no raw audio stored inside `AIInteractionLog` (stores `voicemail:<id>` reference only) | Consent / telecom customer-care fulfillment |
| Staff user and agent accounts | Email, full name, bcrypt password hash, role (`admin`, `supervisor`, `agent`), skills, capacity, active sessions (SHA-256 token hash only) | **No** | While account is active; audit records retained per accountability policy | Bcrypt cost 12 hashing; zero plaintext passwords or raw session tokens stored | Employment / service contract |
| Audit trail (`AuditEvent`) | Actor, entity type/id, action, `old_value`, `new_value`, UTC timestamp | **No** | Configurable compliance retention aligned with operator policy | Append-only audit events accessible only to `supervisor` and `admin` roles; CSV/JSON export rate-limited (`10/60s`) | Legal compliance and security accountability |

---

## 3. Local-First Processing and Data Residency Controls

### 3.1 Zero Third-Party AI Transfer Guarantee

- **No External LLM or Cloud STT Calls:** Both `openai/whisper-large-v3` (via `faster-whisper`) and all four `UBC-NLP/MARBERTv2` classifiers run strictly inside the operator's self-hosted backend and worker containers.
- **No Training Leakage:** Voicemail recordings, transcripts, and tickets are never shared with third-party AI vendors or used to train external foundation models (PRD AI8, Section 10.2).
- **Strict Future Exception Policy:** If an operator ever seeks to introduce an external text model in a future phase, raw audio transfer remains prohibited, direct identifiers must be masked locally before transmission, payloads must be minimized, and a durable written pre-transfer approval tied to exact payload, provider, and purpose is required (PRD Section 10.2).

### 3.2 Data Residency (Egyptian Law No. 151 of 2020, Articles 14-16)

- Cross-border transfer of personal data outside Egypt requires compliance with Law No. 151 of 2020 (adequate protection level and Data Protection Center licensing where applicable).
- SVR is architected to deploy entirely on servers and storage volumes controlled by the telecom operator in their chosen jurisdiction/region (PRD NFR22, Q2), preventing unapproved cross-border transfers by design.
- All Docker services (`postgres`, `redis`, `backend`, `worker`, `frontend`, `prometheus`, `grafana`) communicate over an internal private container network, with encrypted local disk volumes or operator-owned S3-compatible object storage.

---

## 4. Technical and Organizational Security Measures

### 4.1 Encryption at Rest and in Transit (NFR2)

- **Audio Files at Rest:** Every uploaded or browser-recorded voicemail is encrypted with Fernet (`cryptography.fernet.Fernet`: AES-128-CBC with PKCS7 padding + HMAC-SHA256 authentication) before writing to disk (`backend/svr_platform/crypto.py`). Decryption occurs strictly in memory during STT processing or authorized audio streaming.
- **Database and Backups at Rest:** Production deployments enable volume-level / PostgreSQL disk encryption. All backups generated by `ops/backup_restore.py` are packed with a SHA-256 manifest and encrypted with Fernet before being written to backup storage, paired with an outer `.sha256` checksum sidecar.
- **Transport Security:** Production deployments terminate TLS 1.2 or higher at the operator reverse proxy/load balancer, enforcing `SVR_COOKIE_SECURE=true` and `HSTS`.
- **Secrets Management:** `SVR_SECRET_KEY`, `SVR_ENCRYPTION_KEY`, and database credentials are supplied exclusively via environment variables or the operator's secret manager. Production startup aborts if `SVR_SECRET_KEY` or `SVR_ENCRYPTION_KEY` is unset (`backend/svr_platform/config.py`). Zero secrets exist in source code, git history, logs, or frontend bundles.

### 4.2 Access Control, Authentication, and Anti-Abuse (FR22-FR24, NFR1, NFR3)

- **Password Policy:** Bcrypt hashing with cost factor 12 (exceeding NFR1 minimum of 10), minimum 10 characters with mixed case and digits, and rejection of common breached passwords.
- **Session Lifecycle:** Server-tracked sessions (`user_sessions`) delivered via `HttpOnly`, `Secure` (in production), `SameSite=Lax` cookies (`svr_session`). Sessions expire after **8 hours of inactivity** and are revoked immediately upon logout, account deactivation, or role change via `token_version` invalidation.
- **CSRF and CORS Defense:** Cookie-authenticated mutations require double-submit CSRF validation (`svr_csrf` cookie matched against `X-CSRF-Token` header via constant-time comparison) plus `Origin`/`Referer` allowlist checks. CORS never permits wildcard `*` with credentials.
- **Role-Based Access Control and IDOR Prevention:** Every endpoint validates both `role` (`admin`, `supervisor`, `agent`) and `organization_id`. Agents can list, view, update, and play audio strictly for tickets assigned to their own `linked_agent_id`; accessing any other ticket returns HTTP `403 Forbidden`.
- **Rate Limiting and Security Headers:** Sliding-window rate limiting (Redis-backed when configured, memory fallback locally) throttles logins (`10/60s` per IP plus 5-failure account lockout), uploads (`30/60s` per IP), and audit exports (`10/60s`). `SecurityHeadersMiddleware` sets `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and `Permissions-Policy: camera=(), geolocation=(), microphone=(self)`.

### 4.3 Frontend Privacy and Zero Silent Session Replay

- **No Silent Session Replay or Behavioral Trackers:** The Next.js operator application contains zero third-party analytics scripts, zero session replay SDKs (no FullStory, Hotjar, Clarity, or LogRocket), and zero external font/CDN tracking beacons.
- **No Browser Token Storage:** Authentication tokens are never written to `localStorage` or `sessionStorage`.
- **Explicit Microphone Consent:** Browser voicemail recording (`FR2`) accesses the microphone solely upon explicit operator button action, enforces a 60-second cap, and encodes audio locally to 16 kHz mono WAV before authenticated upload.

### 4.4 Retention, Purge, and Auditability

- **Configurable Retention (90-Day Default, Q1):** `SystemSetting.retention_days` defaults to 90 days. Expired encrypted voicemail files and linked ticket records are scheduled for secure deletion according to the operator's configured retention policy, with purge actions logged in `AuditEvent`.
- **Immutable Audit Trail (FR18, NFR19):** Every login, voicemail intake, AI stage execution, label correction (`old_value` -> `new_value`), agent reassignment, status transition, setting change, and audit export is recorded with actor identity and UTC timestamp.

---

## 5. Privacy Risk Assessment and Mitigations

| Risk ID | Threat / Privacy Risk | Likelihood | Impact | Existing Controls and Residual Risk |
|---|---|---|---|---|
| **P1** | Unauthorized access to subscriber voicemail audio or transcripts (IDOR / privilege escalation) | Low | High | Server-side RBAC on every endpoint, Agent ownership check on `/api/tickets/{id}` and `/api/voicemails/{id}/audio`, `organization_id` scoping, Fernet audio encryption at rest. Residual risk: Low. |
| **P2** | Unintended transfer of voice biometric data or PII to third-party AI vendors | Very Low | High | Self-hosted Whisper `large-v3` and MARBERTv2 with zero external AI SDKs or API keys in MVP; network egress can be blocked at firewall. Residual risk: Very Low. |
| **P3** | Automated misrouting or inaccurate classification causing delayed urgent subscriber care | Medium | Medium | Confidence gating (`< 0.5`), null-input guard, taxonomy validation, Human Review Queue, 5% weekly supervisor sampling, immediate auto-routing kill switch, explicit `model` vs `human` provenance (S4). Residual risk: Low. |
| **P4** | Theft or tampering of database / audio backups | Low | High | `ops/backup_restore.py` encrypts every archive with Fernet (`AES-128-CBC + HMAC-SHA256`) and verifies outer and inner SHA-256 checksums before restore. Residual risk: Low. |
| **P5** | Session hijacking, CSRF, or credential stuffing against operator accounts | Low | High | `HttpOnly` `Secure` cookies, 8h inactivity expiry, instant revocation on role/status change, double-submit CSRF + Origin check, bcrypt cost 12, breached-password denylist, sliding-window rate limits + lockout. Residual risk: Low. |
| **P6** | Excessive data retention beyond operational necessity | Medium | Medium | Configurable `retention_days` (default 90 days, Q1) surfaced in `/admin/settings` and documented in `/privacy`; operator enforces scheduled purge job. Residual risk: Low once purge cron is active in production. |

---

## 6. Data Subject Rights Procedure (for Live Production)

Once the operator transitions from the simulated corpus to live subscriber voicemails, the telecom operator (as Data Controller under Egyptian Law No. 151 of 2020) fulfills subscriber requests through internal Admin/Supervisor procedures:

1. **Right to Knowledge and Access:** Supervisors/Admins locate all tickets and transcripts linked to a subscriber request via `AuditEvent` and ticket records; audio is decrypted on-demand only for authorized reviewers.
2. **Right to Rectification:** Supervisors correct inaccurate automated labels via WF2 (`POST /api/tickets/{id}/correct`), immediately recording the human correction and full audit diff.
3. **Right to Erasure / Withdrawal of Consent:** Admins purge the encrypted voicemail file from storage and delete/anonymize associated ticket text records outside mandatory statutory retention logs, logging the erasure event.
4. **Right to Human Intervention:** Subscribers are never contacted by an automated AI; every callback is executed by a trained human care agent, and supervisors can override any priority or routing decision or activate the kill switch at any time.

---

## 7. Pre-Launch Compliance Sign-Off Checklist

Before ingesting real subscriber voicemails (moving beyond the simulated corpus):

- [ ] **Q1 (Retention Period):** Operator legal and operations leads confirm `retention_days` (default 90 days) and activate the automated retention purge schedule.
- [ ] **Q2 (Data Residency and Hosting):** Operator confirms hosting provider, in-region server location, TLS 1.2+ certificates, and encrypted backup storage location.
- [ ] **Q6 (Regulatory Review):** Operator Data Protection Officer (DPO) and Egyptian legal counsel review and sign off this DPIA under Law No. 151 of 2020.
- [ ] **Key Rotation and Secret Store:** Production `SVR_SECRET_KEY` and `SVR_ENCRYPTION_KEY` provisioned via operator secret store (never `.env` defaults), with `SVR_COOKIE_SECURE=true` and `SVR_ENV=production`.
- [ ] **Quarterly Backup/Restore Drill:** First live backup, SHA-256 verification, and restore drill completed and logged (`ops/backup_restore.py`, RPO <= 24h, RTO <= 4h).
