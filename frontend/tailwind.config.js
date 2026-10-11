// Цвета темы лежат в CSS-переменных (hex), а Tailwind не умеет добавлять прозрачность к var():
// классы bg-primary/10, border-primary/20, ring-primary/50 и им подобные (в коде их около 150)
// молча не создавались, и заливки, рамки и свечения, задуманные дизайном, не рисовались.
// color-mix даёт нужную прозрачность для любого значения переменной. Без модификатора
// (bg-primary) Tailwind передаёт вместо числа var(--tw-…-opacity): такой цвет остаётся обычным
// var(--имя), чтобы весь интерфейс не зависел от поддержки color-mix.
const themed = (name) => ({ opacityValue }) =>
  opacityValue === undefined || String(opacityValue).startsWith("var(")
    ? `var(--${name})`
    : `color-mix(in srgb, var(--${name}) calc(${opacityValue} * 100%), transparent)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./pages/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // Доп. брейкпоинты для широких мониторов (2K/4K). Всё, что ≤1536px
      // (ноутбуки/обычные десктопы), не затрагивается — меняется только то,
      // что шире, чтобы контент не «терялся» узкой колонкой по центру.
      screens: {
        '3xl': '1920px',
        '4xl': '2560px',
      },
      fontFamily: {
        display: ["'Melodrama'", "Georgia", "serif"],
        body: ["'General Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      colors: {
        primary:      themed('primary'),
        'primary-dk': themed('primary-dk'),
        'on-primary': themed('on-primary'),
        accent:       themed('accent'),
        'accent-dk':  themed('accent-dk'),
        gold:         themed('gold'),
        bg:           themed('bg'),
        surface:      themed('surface'),
        panel:        themed('panel'),
        text:         themed('text'),
        muted:        themed('muted'),
        faint:        themed('faint'),
        border:       themed('border'),
        success:      themed('success'),
        warning:      themed('warning'),
        error:        themed('error'),
        'card-bg':       themed('card-bg'),
        'card-border':   themed('card-border'),
        'card-text':     themed('card-text'),
        'card-muted':    themed('card-text-muted'),
        'modal-bg':      themed('modal-bg'),
        'modal-text':    themed('modal-text'),
        'modal-overlay': themed('modal-overlay'),
      },
      boxShadow: {
        card:   "0 20px 60px rgba(0,0,0,0.55)",
        // Eye-friendly glow на новой primary #4ade80 — мягкий ореол,
        // не неон. Радиус сокращён с 40 → 12px, чтобы убрать «гало».
        glow:   "0 0 12px rgba(74,222,128,0.30)",
        'glow-lg': "0 0 24px rgba(74,222,128,0.25)",
        ember:  "0 0 14px rgba(244,162,97,0.30)",
        inner:  "inset 0 1px 0 rgba(232,240,234,0.08)",
      },
      animation: {
        float:     "float 8s ease-in-out infinite",
        spinSlow:  "spin 3s linear infinite",
        pulseSlow: "pulse 5s ease-in-out infinite",
        drift:     "drift 30s linear infinite",
        shimmer:   "shimmer 2.5s linear infinite",
        flicker:   "flicker 2.8s ease-in-out infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px) rotate(0deg)" },
          "50%":      { transform: "translateY(-16px) rotate(2deg)" },
        },
        drift: {
          from: { transform: "translateY(0px)" },
          to:   { transform: "translateY(-240px)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        // Свеча-фитиль: лёгкое дрожание пламени для атмосферы кабинета мага.
        flicker: {
          "0%, 100%": { opacity: "1", transform: "scaleY(1) translateX(0)" },
          "25%":      { opacity: "0.86", transform: "scaleY(1.08) translateX(-0.3px)" },
          "50%":      { opacity: "0.96", transform: "scaleY(0.93) translateX(0.3px)" },
          "75%":      { opacity: "0.9",  transform: "scaleY(1.05) translateX(-0.2px)" },
        },
      },
    },
  },
  plugins: [],
};
