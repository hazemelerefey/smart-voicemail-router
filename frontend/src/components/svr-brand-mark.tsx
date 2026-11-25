/* Official SVR App Icon SVG mark */
export function SvrBrandMark({ className = 'size-7' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <rect x="18" y="18" width="476" height="476" rx="100" fill="#C81D20" />
      <path
        d="M105 250a151 151 0 0 1 302 0"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="34"
        strokeLinecap="round"
      />
      <path
        d="M105 250v56a37 37 0 0 0 37 37h17V232h-17a37 37 0 0 0-37 18zm302 0v56a37 37 0 0 1-37 37h-17V232h17a37 37 0 0 1 37 18z"
        fill="#1F2937"
      />
      <path
        d="M198 278v-38m48 95V179m48 156V151m48 127v-48"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="25"
        strokeLinecap="round"
      />
    </svg>
  )
}
