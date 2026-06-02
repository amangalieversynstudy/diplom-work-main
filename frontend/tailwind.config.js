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
        primary:      'var(--primary)',
        'primary-dk': 'var(--primary-dk)',
        accent:       'var(--accent)',
        'accent-dk':  'var(--accent-dk)',
        gold:         'var(--gold)',
        bg:           'var(--bg)',
        surface:      'var(--surface)',
        panel:        'var(--panel)',
        text:         'var(--text)',
        muted:        'var(--muted)',
        faint:        'var(--faint)',
        border:       'var(--border)',
        success:      'var(--success)',
        warning:      'var(--warning)',
        error:        'var(--error)',
        'card-bg':       'var(--card-bg)',
        'card-border':   'var(--card-border)',
        'card-text':     'var(--card-text)',
        'card-muted':    'var(--card-text-muted)',
        'modal-bg':      'var(--modal-bg)',
        'modal-text':    'var(--modal-text)',
        'modal-overlay': 'var(--modal-overlay)',
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
