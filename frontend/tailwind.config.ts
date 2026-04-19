import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#06080b",
        panel: "#0d1116",
        panel2: "#11161d",
        border: "#1a212b",
        border2: "#232b38",
        muted: "#6b7582",
        mute2: "#9aa4b2",
        ink: "#e6e9ef",
        inkhi: "#ffffff",
        red: "#e05561",
        amber: "#e4a017",
        green: "#3fb27f",
        blue: "#4d9eff",
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
      },
    },
  },
  plugins: [],
};
export default config;
