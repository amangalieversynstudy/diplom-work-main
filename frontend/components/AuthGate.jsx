/**
 * Герб над формой входа/регистрации ("Врата академии"): арка с руной-звездой.
 * Статичный, декоративный; цвета только из токенов пергамента.
 */
export default function AuthGate({ className = "" }) {
  return (
    <svg
      viewBox="0 0 120 84"
      className={`mx-auto mb-3 h-20 w-auto ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M16 80 V40 a44 36 0 0 1 88 0 V80"
        fill="none"
        stroke="var(--gold-frame)"
        strokeWidth="5"
        strokeLinejoin="round"
      />
      <path
        d="M28 80 V42 a32 26 0 0 1 64 0 V80"
        fill="var(--ink-deep)"
        stroke="var(--parchment)"
        strokeWidth="2"
      />
      <path
        d="M60 26 L64 38 L76 38 L66 46 L70 58 L60 50 L50 58 L54 46 L44 38 L56 38 Z"
        fill="var(--parchment-light)"
        stroke="var(--gold-frame)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M10 80 H110" stroke="var(--gold-frame)" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}
