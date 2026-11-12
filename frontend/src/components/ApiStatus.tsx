"use client";

import { useEffect, useState } from "react";
import { messages as t } from "@/i18n/en";

type Health = {
  status: "ok" | "degraded";
  database: { schema_revision: string | null; sqlite_version: string; connected: boolean };
};

type State = { kind: "checking" } | { kind: "unreachable" } | { kind: "loaded"; health: Health };

export function ApiStatus() {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/health", { cache: "no-store" })
      .then(async (r) => {
        const body = (await r.json()) as Health;
        if (!cancelled) setState({ kind: "loaded", health: body });
      })
      .catch(() => !cancelled && setState({ kind: "unreachable" }));
    return () => {
      cancelled = true;
    };
  }, []);

  let label: string = t.status.checking;
  let tone = "border-olive";
  if (state.kind === "unreachable") {
    label = t.status.unreachable;
    tone = "border-terracotta";
  } else if (state.kind === "loaded") {
    label = state.health.status === "ok" ? t.status.ok : t.status.degraded;
    tone = state.health.status === "ok" ? "border-olive" : "border-terracotta";
  }

  return (
    <div role="status" aria-live="polite" data-testid="api-status" data-state={state.kind === "loaded" ? state.health.status : state.kind}
      className={`rounded-lg border-2 ${tone} bg-surface p-4`}>
      <p className="font-semibold">{label}</p>
      {state.kind === "loaded" && (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 text-sm">
          <dt>{t.status.schema}</dt>
          <dd data-testid="schema-revision">{state.health.database.schema_revision ?? "—"}</dd>
          <dt>{t.status.sqlite}</dt>
          <dd>{state.health.database.sqlite_version}</dd>
        </dl>
      )}
    </div>
  );
}
