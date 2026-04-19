import type {
  ExecutiveActionQueueOutput,
  ExecutiveAlertsOutput,
  ExecutiveBriefingOutput,
} from "@/types/api";
import {
  ActionQueueView,
  AlertListView,
  BriefingView,
} from "@/components/executive";

export function ExecutiveBriefingOutputView({
  output,
}: {
  output: ExecutiveBriefingOutput;
}) {
  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
      </header>
      <BriefingView briefing={output.briefing} />
    </div>
  );
}

export function ExecutiveActionQueueOutputView({
  output,
}: {
  output: ExecutiveActionQueueOutput;
}) {
  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
      </header>
      <ActionQueueView queue={output.queue} />
    </div>
  );
}

export function ExecutiveAlertsOutputView({
  output,
}: {
  output: ExecutiveAlertsOutput;
}) {
  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
      </header>
      <AlertListView bundle={output.alerts} />
    </div>
  );
}
