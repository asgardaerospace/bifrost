"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CommandInput } from "@/components/command-console/command-input";
import { CommandHistory } from "@/components/command-console/command-history";
import { ResponseRenderer } from "@/components/outputs/response-renderer";
import { api } from "@/lib/api";
import { Panel, Pill } from "@/components/ui";
import type { CommandResponse } from "@/types/api";

export default function ConsolePage() {
  const qc = useQueryClient();
  const [response, setResponse] = useState<CommandResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (text: string) => api.submitCommand({ text }),
    onSuccess: (res) => {
      setResponse(res);
      qc.invalidateQueries({ queryKey: ["command-history"] });
    },
  });

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <header>
          <h1 className="text-xl font-semibold">Command Console</h1>
          <p className="mt-1 text-sm text-muted">
            Controlled command interface for investor operations.
          </p>
        </header>

        <CommandInput
          onSubmit={(text) => mutation.mutate(text)}
          busy={mutation.isPending}
        />

        {mutation.isError && (
          <Panel title="Error">
            <div className="text-sm text-danger">
              {mutation.error instanceof Error
                ? mutation.error.message
                : "Command failed."}
            </div>
          </Panel>
        )}

        {mutation.isPending && (
          <Panel title="Running">
            <div className="text-sm text-muted">Routing command…</div>
          </Panel>
        )}

        {response && !mutation.isPending && (
          <>
            <ResponseMeta response={response} />
            <ResponseRenderer output={response.output} />
          </>
        )}
      </div>

      <aside>
        <CommandHistory />
      </aside>
    </div>
  );
}

function ResponseMeta({ response }: { response: CommandResponse }) {
  const c = response.classification;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill tone="accent">{c.command_class}</Pill>
      <Pill>{c.intent}</Pill>
      <Pill
        tone={
          c.confidence === "high"
            ? "ok"
            : c.confidence === "medium"
              ? "warn"
              : "danger"
        }
      >
        confidence: {c.confidence}
      </Pill>
      {c.referenced_entity && (
        <Pill>
          entity: {c.referenced_entity.label ?? c.referenced_entity.entity_type}
        </Pill>
      )}
      <span className="font-mono text-[11px] text-muted">
        {response.duration_ms}ms
      </span>
    </div>
  );
}
