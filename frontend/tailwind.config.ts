import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#04070c",
        bgdeep: "#020407",
        panel: "#0a0f17",
        panel2: "#0f1520",
        panel3: "#131b28",
        border: "#17202f",
        border2: "#1f2c42",
        border3: "#2a3d5c",
        muted: "#5a6677",
        mute2: "#8d99ac",
        ink: "#d8dfec",
        inkhi: "#f3f6fb",
        red: "#ff5a6b",
        amber: "#f0b429",
        green: "#3fd29a",
        blue: "#4d9eff",
        cyan: "#22d3ee",
        teal: "#2dd4bf",
        accent: "#22d3ee",
        accent2: "#0ea5b7",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,0.25), 0 0 18px -4px rgba(34,211,238,0.35)",
        "glow-sm": "0 0 0 1px rgba(34,211,238,0.2), 0 0 10px -2px rgba(34,211,238,0.25)",
        "glow-red": "0 0 0 1px rgba(255,90,107,0.3), 0 0 18px -4px rgba(255,90,107,0.4)",
        "glow-amber": "0 0 0 1px rgba(240,180,41,0.3), 0 0 18px -4px rgba(240,180,41,0.35)",
        "inset-glow": "inset 0 0 40px -8px rgba(34,211,238,0.15)",
        panel: "0 1px 0 rgba(255,255,255,0.02) inset, 0 0 0 1px rgba(34,211,238,0.04)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica",
          "Arial",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["10px", "14px"],
        xs: ["11px", "15px"],
        sm: ["12px", "16px"],
        base: ["13px", "18px"],
        md: ["14px", "19px"],
        lg: ["16px", "22px"],
        xl: ["20px", "26px"],
        "2xl": ["28px", "34px"],
      },
      keyframes: {
        corePulse: {
          "0%,100%": {
            boxShadow:
              "0 0 0 0 rgba(34,211,238,0.35), 0 0 40px -6px rgba(34,211,238,0.4), inset 0 0 30px -8px rgba(34,211,238,0.35)",
          },
          "50%": {
            boxShadow:
              "0 0 0 6px rgba(34,211,238,0.0), 0 0 70px -4px rgba(34,211,238,0.55), inset 0 0 44px -6px rgba(34,211,238,0.5)",
          },
        },
        coreRing: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          from: { opacity: "0", transform: "translateX(8px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        slideInUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        softPulse: {
          "0%,100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        flashOk: {
          "0%": { backgroundColor: "rgba(63,210,154,0.25)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        "core-pulse": "corePulse 3.6s ease-in-out infinite",
        "core-ring": "coreRing 24s linear infinite",
        "fade-in": "fadeIn 240ms ease-out both",
        "slide-in-right": "slideInRight 220ms ease-out both",
        "slide-in-up": "slideInUp 220ms ease-out both",
        scan: "scan 6s linear infinite",
        "soft-pulse": "softPulse 2.4s ease-in-out infinite",
        "flash-ok": "flashOk 900ms ease-out both",
      },
    },
  },
  plugins: [],
};
export default config;
