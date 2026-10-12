// Портреты классов героя: пиксель-арт 16x16 (маг, арканист, рейнджер) на круглом медальоне
// с цветом класса. Цвета только из токенов; рисунок статичный и декоративный.
import { PIXEL_ART, PIXEL_FILL, PIXEL_SIZE } from "../lib/classPixels";

const ROLE_BY_PK = { 1: "python", 2: "django", 3: "devops" };

const ACCENT = {
  python: "var(--gold-frame)",
  django: "var(--primary)",
  devops: "var(--wax)",
};

// Пиксели одной строки склеиваются в прямоугольники одного цвета.
function runsOf(row) {
  const out = [];
  let i = 0;
  while (i < row.length) {
    const ch = row[i];
    let j = i;
    while (j < row.length && row[j] === ch) j++;
    if (ch !== ".") out.push({ ch, x: i, w: j - i });
    i = j;
  }
  return out;
}

const CELL = 3; // 16 пикселей по 3 единицы = 48 из 64, по центру медальона
const OFFSET = (64 - PIXEL_SIZE * CELL) / 2;

function PixelFigure({ role }) {
  const rows = PIXEL_ART[role];
  return (
    <g shapeRendering="crispEdges">
      {rows.flatMap((row, y) =>
        runsOf(row).map(({ ch, x, w }) => (
          <rect
            key={`${y}-${x}`}
            x={OFFSET + x * CELL}
            y={OFFSET + y * CELL}
            width={w * CELL}
            height={CELL}
            fill={PIXEL_FILL[ch]}
          />
        )),
      )}
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
        {known ? <PixelFigure role={known} /> : (
          <text x="32" y="43" textAnchor="middle" fontSize="30" fill="var(--ink)">?</text>
        )}
      </g>
    </svg>
  );
}
