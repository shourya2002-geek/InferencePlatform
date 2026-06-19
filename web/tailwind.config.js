/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Engineering dark surface scale (GitHub Primer / Grafana inspired).
        ink: {
          900: "#0a0c10", // app background
          850: "#0d1017",
          800: "#11151d", // panel
          750: "#141923",
          700: "#1a202c", // raised panel
          600: "#222a38",
        },
        line: {
          DEFAULT: "#1e2733", // hairline border
          strong: "#2b3544",
          faint: "#161c26",
        },
        fg: {
          DEFAULT: "#e6edf3", // primary text
          muted: "#9aa7b8",
          faint: "#677386",
        },
        // PyTorch orange — used sparingly as the brand accent.
        torch: {
          DEFAULT: "#ee4c2c",
          soft: "#f2724f",
          dim: "rgba(238,76,44,0.14)",
        },
        // Status / semantic colors.
        ok: "#3fb950",
        warn: "#d29922",
        danger: "#f85149",
        info: "#58a6ff",
        violet: "#a371f7",
        teal: "#2dd4bf",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "0.9rem" }],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02), 0 2px 12px -4px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(238,76,44,0.4), 0 0 22px -6px rgba(238,76,44,0.5)",
      },
      keyframes: {
        "pulse-line": {
          "0%, 100%": { opacity: "0.25" },
          "50%": { opacity: "1" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "pulse-line": "pulse-line 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
