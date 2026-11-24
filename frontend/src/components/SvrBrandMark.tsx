"use client";

/* Official SVR App Icon SVG mark from SVR Presentation Design System */
export function SvrBrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="18" y="18" width="476" height="476" rx="100" fill="var(--accent)" />
      <path
        d="M105 250a151 151 0 0 1 302 0"
        fill="none"
        stroke="var(--accent-on)"
        strokeWidth="34"
        strokeLinecap="round"
      />
      <path
        d="M105 250v56a37 37 0 0 0 37 37h17V232h-17a37 37 0 0 0-37 18zm302 0v56a37 37 0 0 1-37 37h-17V232h17a37 37 0 0 1 37 18z"
        fill="var(--svr-charcoal, #1F2937)"
      />
      <path
        d="M198 278v-38m48 95V179m48 156V151m48 127v-48"
        fill="none"
        stroke="var(--accent-on)"
        strokeWidth="25"
        strokeLinecap="round"
      />
    </svg>
  );
}
