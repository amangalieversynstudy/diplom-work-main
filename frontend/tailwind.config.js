/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Cinzel Decorative'", "serif"],
        body: ["'Space Grotesk'", "sans-serif"],
      },
      colors: {
        primary: "#7C3AED",
        accent: "#22D3EE",
        gold: "#F59E0B",
        bg: "#0F1226",
        surface: "#1B2040",
        success: "#10B981",
        warning: "#F59E0B",
        error: "#EF4444",
        obsidian: "#0b0d1b",
        nebula: "#312e81",
        aurora: "#4f46e5",
        crystal: "#34d399",
        ember: "#f97316",
      },
      boxShadow: {
        card: "0 20px 60px rgba(0,0,0,0.45)",
        glow: "0 0 40px rgba(34,211,238,0.35)",
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        pulseSlow: "pulse 4s ease-in-out infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
};
