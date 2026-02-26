export default function AuditPage() {
  const architectureMermaid = `graph TD
  subgraph "Engine Layer (Port 8100)"
    E[Engine Core] --> W[Watchdog]
    E --> API[REST API / WS Server]
  end

  subgraph "Contract Layer (Constitution)"
    C{S7-DASHBOARD-CONTRACT.md}
  end

  subgraph "UI Layer (Port 3001)"
    UI[NEXT-TRADE-UI]
    UI --> CC[Command Center]
    UI --> OR[Ops Runtime]
    UI --> AU[Audit]
  end

  API -.->|Schema Validated| C
  C -.->|Standard Interface| UI`;

  return (
    <main
      className="min-h-screen bg-bg text-text"
      style={{ padding: "calc(var(--space-base) * 3)" }}
    >
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-text-strong">
          Audit / Evidence
        </h1>
        <p className="text-sm text-muted">
          Contract-bound evidence and reporting surface
        </p>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{ padding: "calc(var(--space-base) * 2)" }}
        >
          <h2 className="text-lg font-semibold text-text-strong">
            Evidence Feed
          </h2>
        </article>
        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{ padding: "calc(var(--space-base) * 2)" }}
        >
          <h2 className="text-lg font-semibold text-text-strong">
            Audit Timeline
          </h2>
        </article>
        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{ padding: "calc(var(--space-base) * 2)" }}
        >
          <h2 className="text-lg font-semibold text-text-strong">
            Report Snapshot
          </h2>
        </article>
      </section>

      <section className="mt-4">
        <article
          className="rounded-lg border border-border-subtle bg-panel"
          style={{ padding: "calc(var(--space-base) * 2)" }}
        >
          <h2 className="text-lg font-semibold text-text-strong mb-2">
            System Info (Architecture)
          </h2>
          <p className="text-sm text-muted mb-3">
            Contract-first decoupled architecture for investor demo
          </p>
          <pre className="text-xs text-muted overflow-auto">{`\`\`\`mermaid\n${architectureMermaid}\n\`\`\``}</pre>
        </article>
      </section>
    </main>
  );
}
