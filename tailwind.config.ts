import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        nt: {
          bg: "var(--nt-bg)",
          surface: "var(--nt-surface)",
          "surface-2": "var(--nt-surface-2)",
          border: "var(--nt-border)",
          fg: "var(--nt-fg)",
          "fg-2": "var(--nt-fg-2)",
          up: "var(--nt-up)",
          down: "var(--nt-down)",
          warn: "var(--nt-warn)",
          info: "var(--nt-info)",
        },
        bg: "var(--bg)",
        panel: "var(--panel)",
        "panel-2": "var(--panel-2)",
        border: "var(--border)",
        "border-subtle": "var(--border-subtle)",
        text: "var(--text)",
        "text-strong": "var(--text-strong)",
        muted: "var(--muted)",
        "muted-dark": "var(--muted-dark)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--danger)",
        "health-ok": "var(--health-ok)",
        "health-warn": "var(--health-warn)",
        "alert-critical": "var(--alert-critical)",
        info: "var(--info)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        card: "var(--panel)",
        "card-foreground": "var(--text)",
        "muted-foreground": "var(--muted)",
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "var(--radius-sm)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        DEFAULT: "var(--shadow)",
        sm: "var(--shadow-sm)",
      },
    },
  },
  plugins: [],
};
export default config;
