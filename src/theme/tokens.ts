export const tokens = {
  color: {
    bg: "#0a0e1a",
    panel: "#111827",
    panel2: "#1e293b",
    border: "#334155",
    borderSubtle: "#1e293b",
    text: "#e5e7eb",
    textStrong: "#f9fafb",
    muted: "#94a3b8",
    mutedDark: "#64748b",
    ok: "#22c55e",
    warn: "#f59e0b",
    danger: "#ef4444",
    info: "#06b6d4",
    accent: "#3b82f6",
    accentHover: "#2563eb",
    healthOk: "#22c55e",
    healthWarn: "#f59e0b",
    alertCritical: "#ef4444",
  },
  spacing: {
    base: 8,
    md: 12,
    lg: 16,
  },
  radius: {
    default: "12px",
    sm: "8px",
    lg: "16px",
  },
  shadow: {
    default: "0 4px 12px rgba(0, 0, 0, 0.3)",
    sm: "0 2px 6px rgba(0, 0, 0, 0.2)",
  },
} as const;

export const buildTokenCss = () => `
:root {
  --bg: ${tokens.color.bg};
  --panel: ${tokens.color.panel};
  --panel-2: ${tokens.color.panel2};
  --border: ${tokens.color.border};
  --border-subtle: ${tokens.color.borderSubtle};
  --text: ${tokens.color.text};
  --text-strong: ${tokens.color.textStrong};
  --muted: ${tokens.color.muted};
  --muted-dark: ${tokens.color.mutedDark};
  --ok: ${tokens.color.ok};
  --warn: ${tokens.color.warn};
  --danger: ${tokens.color.danger};
  --info: ${tokens.color.info};
  --accent: ${tokens.color.accent};
  --accent-hover: ${tokens.color.accentHover};
  --health-ok: ${tokens.color.healthOk};
  --health-warn: ${tokens.color.healthWarn};
  --alert-critical: ${tokens.color.alertCritical};
  --radius: ${tokens.radius.default};
  --radius-sm: ${tokens.radius.sm};
  --radius-lg: ${tokens.radius.lg};
  --shadow: ${tokens.shadow.default};
  --shadow-sm: ${tokens.shadow.sm};
  --space-base: ${tokens.spacing.base}px;
}
`;
