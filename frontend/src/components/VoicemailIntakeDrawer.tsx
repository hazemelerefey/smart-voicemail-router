"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  IconAlertCircle,
  IconCheck,
  IconMicrophone,
  IconPlayerStop,
  IconTrash,
  IconUpload,
  IconX,
} from "@tabler/icons-react";
import { api, ApiError } from "@/lib/api";
import { UI_COPY, type Locale } from "@/lib/i18n";
import { formatDuration } from "@/lib/taxonomy";
import type { VoicemailUploadResponse } from "@/lib/types";
import { BrowserWavRecorder, MAX_RECORDING_SECONDS } from "@/lib/wavRecorder";

interface VoicemailIntakeDrawerProps {
  open: boolean;
  locale: Locale;
  onClose: () => void;
  onSubmitted: (res: VoicemailUploadResponse) => void;
}

const MAX_BYTES = 25 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a"];

export function VoicemailIntakeDrawer({
  open,
  locale,
  onClose,
  onSubmitted,
}: VoicemailIntakeDrawerProps) {
  const t = UI_COPY[locale];
  const [mode, setMode] = useState<"upload" | "record">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [recordedFile, setRecordedFile] = useState<File | null>(null);
  const [recordedDuration, setRecordedDuration] = useState<number>(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<VoicemailUploadResponse | null>(null);

  const recorderRef = useRef<BrowserWavRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (recorderRef.current) recorderRef.current.abort();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  if (!open) return null;

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleStopRecording = async () => {
    stopTimer();
    setRecording(false);
    const rec = recorderRef.current;
    if (!rec) return;
    try {
      const result = await rec.stop();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const url = URL.createObjectURL(result.blob);
      setPreviewUrl(url);
      setRecordedFile(result.file);
      setRecordedDuration(result.durationSeconds);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to finalize WAV recording.";
      setError(message);
    }
  };

  const handleStartRecording = async () => {
    setError(null);
    setSuccessInfo(null);
    setRecordedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    try {
      const rec = new BrowserWavRecorder();
      recorderRef.current = rec;
      await rec.start();
      setRecording(true);
      setElapsedSec(0);
      const startedAt = Date.now();
      timerRef.current = setInterval(() => {
        const secs = Math.floor((Date.now() - startedAt) / 1000);
        setElapsedSec(secs);
        if (secs >= MAX_RECORDING_SECONDS) {
          void handleStopRecording();
        }
      }, 250);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : locale === "ar"
            ? "تعذر الوصول إلى الميكروفون."
            : "Could not access the microphone.";
      setError(msg);
      setRecording(false);
    }
  };

  const handleFileChange = (ev: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccessInfo(null);
    const file = ev.target.files?.[0] || null;
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const lower = file.name.toLowerCase();
    const validExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
    if (!validExt) {
      setError(
        locale === "ar"
          ? "صيغة الملف غير مدعومة. الصيغ المقبولة هي WAV أو MP3 أو M4A."
          : "Unsupported audio format. Please upload a WAV, MP3, or M4A file."
      );
      setSelectedFile(null);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(
        locale === "ar"
          ? "حجم الملف يتجاوز الحد الأقصى 25 ميجابايت."
          : "File size exceeds the 25 MB limit."
      );
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const activeFile = mode === "upload" ? selectedFile : recordedFile;

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!activeFile) {
      setError(
        locale === "ar"
          ? "يرجى اختيار ملف صوتي أو تسجيل رسالة أولا."
          : "Please choose an audio file or record a voicemail first."
      );
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const idempotencyKey =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-${activeFile.name}`;
      const res = await api.uploadVoicemail(activeFile, idempotencyKey);
      setSuccessInfo(res);
      setSelectedFile(null);
      setRecordedFile(null);
      onSubmitted(res);
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? err.detail
          : err instanceof Error
            ? err.message
            : "Voicemail upload failed.";
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="drawer-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="intake-drawer-title"
      onClick={(ev) => {
        if (ev.target === ev.currentTarget && !recording && !submitting) onClose();
      }}
    >
      <div className="drawer-panel">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <h2 id="intake-drawer-title" style={{ margin: 0 }}>
            {t.intakeTitle}
          </h2>
          <button
            type="button"
            className="btn ghost"
            aria-label={locale === "ar" ? "إغلاق" : "Close intake panel"}
            onClick={onClose}
            disabled={recording || submitting}
          >
            <IconX size={20} stroke={1.8} aria-hidden="true" />
          </button>
        </div>

        <p className="sub" style={{ margin: 0 }}>
          {t.intakeSub}
        </p>

        <div className="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            className="tab"
            aria-selected={mode === "upload"}
            onClick={() => {
              setMode("upload");
              setError(null);
            }}
            disabled={recording}
          >
            <IconUpload size={16} stroke={1.8} aria-hidden="true" />
            <span>{t.intakeTabUpload}</span>
          </button>
          <button
            type="button"
            role="tab"
            className="tab"
            aria-selected={mode === "record"}
            onClick={() => {
              setMode("record");
              setError(null);
            }}
          >
            <IconMicrophone size={16} stroke={1.8} aria-hidden="true" />
            <span>{t.intakeTabRecord}</span>
          </button>
        </div>

        <p className="card-note" style={{ margin: 0 }}>
          {t.intakeSpec}
        </p>

        {error && (
          <div className="alert error" role="alert">
            <IconAlertCircle size={18} stroke={1.8} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {successInfo && (
          <div className="alert ok" role="status">
            <IconCheck size={18} stroke={1.8} aria-hidden="true" />
            <div>
              <div>
                {locale === "ar"
                  ? `تم إنشاء التذكرة (${successInfo.status}) وبدأت المعالجة.`
                  : `Ticket queued (${successInfo.status}) for pipeline processing.`}
              </div>
              <div className="mono" style={{ marginTop: 4 }}>
                {successInfo.ticket_id}
              </div>
              {successInfo.recommendation_note && (
                <div style={{ marginTop: 4 }}>{successInfo.recommendation_note}</div>
              )}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {mode === "upload" ? (
            <label className="field">
              <span>{locale === "ar" ? "ملف الرسالة الصوتية" : "Voicemail Audio File"}</span>
              <input
                type="file"
                accept=".wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a"
                onChange={handleFileChange}
                disabled={submitting}
              />
              {selectedFile && (
                <span className="mono muted num">
                  {selectedFile.name} · {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </span>
              )}
            </label>
          ) : (
            <div className="card-surface" style={{ margin: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 12,
                }}
              >
                <span className="muted" style={{ fontWeight: 600 }}>
                  {locale === "ar" ? "تسجيل 16 kHz WAV أحادي" : "16 kHz Mono WAV Recorder"}
                </span>
                <span className={`mono num ${recording ? "urgent-text" : "muted"}`}>
                  {elapsedSec}s / {MAX_RECORDING_SECONDS}s
                </span>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {!recording ? (
                  <button
                    type="button"
                    className="btn"
                    onClick={handleStartRecording}
                    disabled={submitting}
                  >
                    <IconMicrophone size={17} stroke={1.8} aria-hidden="true" />
                    <span>{locale === "ar" ? "بدء التسجيل" : "Start Recording"}</span>
                  </button>
                ) : (
                  <button type="button" className="btn danger" onClick={handleStopRecording}>
                    <IconPlayerStop size={17} stroke={1.8} aria-hidden="true" />
                    <span>{locale === "ar" ? "إيقاف التسجيل" : "Stop Recording"}</span>
                  </button>
                )}

                {recordedFile && !recording && (
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => {
                      setRecordedFile(null);
                      if (previewUrl) {
                        URL.revokeObjectURL(previewUrl);
                        setPreviewUrl(null);
                      }
                    }}
                  >
                    <IconTrash size={17} stroke={1.8} aria-hidden="true" />
                    <span>{locale === "ar" ? "مسح" : "Discard"}</span>
                  </button>
                )}
              </div>

              {previewUrl && recordedFile && (
                <div style={{ marginTop: 12 }}>
                  <audio controls src={previewUrl} style={{ width: "100%" }} />
                  <div className="mono muted num" style={{ marginTop: 6 }}>
                    {recordedFile.name} · {formatDuration(recordedDuration)} ·{" "}
                    {(recordedFile.size / 1024).toFixed(1)} KB
                  </div>
                  {recordedDuration > 0 && recordedDuration < 15 && (
                    <p className="card-note high-text">
                      {locale === "ar"
                        ? "ملاحظة: التسجيل أقل من 15 ثانية (سيتم قبوله، لكن يفضل 15 إلى 60 ثانية)."
                        : "Note: Clip is shorter than 15s (accepted; 15 to 60s is recommended)."}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 6 }}>
            <button
              type="button"
              className="btn"
              onClick={onClose}
              disabled={recording || submitting}
            >
              {t.cancel}
            </button>
            <button
              type="submit"
              className="btn primary"
              disabled={!activeFile || recording || submitting}
            >
              {submitting ? t.intakeSubmitting : t.intakeSubmit}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
