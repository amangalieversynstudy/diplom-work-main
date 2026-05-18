/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./pages/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
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
      },
      boxShadow: {
        card:   "0 20px 60px rgba(0,0,0,0.55)",
        glow:   "0 0 40px rgba(46,204,138,0.25)",
        ember:  "0 0 40px rgba(232,105,58,0.3)",
        inner:  "inset 0 1px 0 rgba(232,240,234,0.08)",
      },
      animation: {
        float:     "float 8s ease-in-out infinite",
        pulseSlow: "pulse 5s ease-in-out infinite",
        drift:     "drift 30s linear infinite",
        shimmer:   "shimmer 2.5s linear infinite",
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
      },
    },
  },
  plugins: [],
};
