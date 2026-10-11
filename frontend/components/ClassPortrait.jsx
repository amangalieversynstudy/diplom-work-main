// Портреты классов героя: силуэты в тёмных чернилах на круглом медальоне с цветом класса.
// Цвета только из токенов пергамента; рисунок статичный и декоративный.
const ROLE_BY_PK = { 1: "python", 2: "django", 3: "devops" };

const ACCENT = {
  python: "var(--gold-frame)",
  django: "var(--primary)",
  devops: "var(--wax)",
};

function Silhouette({ role }) {
  const ink = "var(--ink-deep)";
  if (role === "django") {
    // арканист: капюшон, мантия, раскрытая книга
    return (
      <g fill={ink}>
        <path d="M32 9c-7 0-11 5-11 12 0 3 1 5 3 7l-6 12v14h28V40l-6-12c2-2 3-4 3-7 0-7-4-12-11-12z" />
        <ellipse cx="32" cy="24" rx="5" ry="6" fill="var(--parchment)" />
        <path d="M18 44l14 5 14-5v8l-14 4-14-4z" fill="var(--parchment-light)" stroke={ink} strokeWidth="1.5" />
        <path d="M32 49v7" stroke={ink} strokeWidth="1.5" />
      </g>
    );
  }
  if (role === "devops") {
    // рейнджер: капюшон-кепка, плащ, шестерня за плечом
    return (
      <g fill={ink}>
        <circle cx="46" cy="20" r="8" fill="none" stroke={ink} strokeWidth="3" strokeDasharray="3.2 2.6" />
        <circle cx="46" cy="20" r="3" />
        <path d="M24 12c0-4 3-6 7-6s7 2 7 6l2 3H22z" />
        <circle cx="31" cy="21" r="6" />
        <path d="M31 27c-8 0-13 5-13 12v17h26V39c0-7-5-12-13-12z" />
        <path d="M18 56l-4-4M44 56l4-4" stroke={ink} strokeWidth="2.5" strokeLinecap="round" />
      </g>
    );
  }
  // python: маг с остроконечной шляпой и посохом
  return (
    <g fill={ink}>
      <path d="M32 4l9 17H23z" />
      <ellipse cx="32" cy="21" rx="13" ry="3" />
      <circle cx="32" cy="29" r="6" />
      <path d="M32 35c-8 0-13 5-13 12v9h26v-9c0-7-5-12-13-12z" />
      <path d="M50 14v42" stroke={ink} strokeWidth="3" strokeLinecap="round" />
      <circle cx="50" cy="12" r="4" fill="var(--gold-frame)" stroke={ink} strokeWidth="1.5" />
    </g>
  );
}

/**
 * @param {{role: "python"|"django"|"devops"|1|2|3|null, size?: number, className?: string, label?: string}} props
 */
export default function ClassPortrait({ role, size = 96, className = "", label }) {
  const key = ROLE_BY_PK[role] || role;
  const known = ACCENT[key] ? key : null;
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : "true"}
      focusable="false"
    >
      <circle cx="32" cy="32" r="30" fill="var(--parchment)" stroke={known ? ACCENT[known] : "var(--gold-frame)"} strokeWidth="3" />
      <circle cx="32" cy="32" r="26" fill="none" stroke="var(--ink)" strokeWidth="0.8" opacity="0.5" />
      <clipPath id={`cp-${known || "none"}`}>
        <circle cx="32" cy="32" r="27" />
      </clipPath>
      <g clipPath={`url(#cp-${known || "none"})`}>
        {known ? <Silhouette role={known} /> : (
          <text x="32" y="43" textAnchor="middle" fontSize="30" fill="var(--ink)">?</text>
        )}
      </g>
    </svg>
  );
}
