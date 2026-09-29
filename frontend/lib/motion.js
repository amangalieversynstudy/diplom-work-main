// Пользователь просил в системе уменьшить движение (prefers-reduced-motion).
export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
