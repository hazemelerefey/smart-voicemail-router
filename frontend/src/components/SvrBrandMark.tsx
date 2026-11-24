"use client";

/* Geometric vector SVG brand mark for SVR: incoming voicemail wave routed into priority tracks */
export function SvrBrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="1"
        y="1"
        width="26"
        height="26"
        rx="6"
        stroke="currentColor"
        strokeWidth="1.65"
      />
      {/* Left signal waveform */}
      <path
        d="M5.5 14H8L9.6 9.5L11.6 18.5L13.3 14H15"
        stroke="var(--accent)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Route split node */}
      <rect x="14.5" y="12.5" width="3" height="3" rx="0.75" fill="currentColor" />
      {/* Two routed output channels */}
      <path
        d="M17.5 14H20L22.5 9.5M17.5 14H20L22.5 18.5"
        stroke="currentColor"
        strokeWidth="1.65"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="21.5" y="8" width="2.5" height="2.5" rx="0.6" fill="var(--accent)" />
      <rect x="21.5" y="17.5" width="2.5" height="2.5" rx="0.6" fill="currentColor" />
    </svg>
  );
}
