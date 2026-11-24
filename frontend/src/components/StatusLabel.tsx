"use client";

import {
  IconAlertCircle,
  IconAlertTriangle,
  IconCheck,
  IconCircleCheck,
  IconClock,
  IconLock,
  IconPlayerPlay,
  IconUserOff,
} from "@tabler/icons-react";
import { labelForBucket, labelForStatus, type Locale } from "@/lib/i18n";

export function TicketStatusText({ status, locale }: { status: string; locale: Locale }) {
  const label = labelForStatus(status, locale);
  switch (status) {
    case "failed":
      return (
        <span className="status-inline urgent-text">
          <IconAlertCircle size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "unassigned":
      return (
        <span className="status-inline high-text">
          <IconUserOff size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "processing":
    case "received":
      return (
        <span className="status-inline info-text">
          <IconClock size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "in_progress":
      return (
        <span className="status-inline info-text">
          <IconPlayerPlay size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "ready":
      return (
        <span className="status-inline ok-text">
          <IconCircleCheck size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "resolved":
      return (
        <span className="status-inline ok-text">
          <IconCheck size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    case "closed":
      return (
        <span className="status-inline muted">
          <IconLock size={15} stroke={1.8} aria-hidden="true" />
          {label}
        </span>
      );
    default:
      return <span className="status-inline muted">{label}</span>;
  }
}

export function BucketText({ bucket, locale }: { bucket: string | null | undefined; locale: Locale }) {
  if (!bucket) return <span className="muted">-</span>;
  const label = labelForBucket(bucket, locale);
  if (bucket === "urgent") {
    return (
      <span className="status-inline urgent-text">
        <IconAlertTriangle size={14} stroke={2} aria-hidden="true" />
        {label}
      </span>
    );
  }
  if (bucket === "high") {
    return <span className="status-inline high-text">{label}</span>;
  }
  if (bucket === "normal") {
    return <span className="status-inline info-text">{label}</span>;
  }
  return <span className="status-inline muted">{label}</span>;
}

export function bucketColorClass(bucket: string | null | undefined): string {
  if (bucket === "urgent") return "urgent-text";
  if (bucket === "high") return "high-text";
  if (bucket === "normal") return "info-text";
  return "faint";
}
