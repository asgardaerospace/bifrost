import type { CommandOutput } from "@/types/api";
import { SummaryOutputView } from "./summary-output";
import { RankedOutputView } from "./ranked-output";
import { DraftOutputView } from "./draft-output";
import { ReviewOutputView } from "./review-output";
import { WorkflowOutputView } from "./workflow-output";
import { EngineListOutputView } from "./engine-list-output";
import { MarketListOutputView } from "./market-list-output";
import { ProgramListOutputView } from "./program-list-output";
import { SupplierListOutputView } from "./supplier-list-output";
import {
  ExecutiveActionQueueOutputView,
  ExecutiveAlertsOutputView,
  ExecutiveBriefingOutputView,
} from "./executive-output";
import { ClarificationOutputView } from "./clarification-output";
import { UnsupportedOutputView } from "./unsupported-output";

export function ResponseRenderer({ output }: { output: CommandOutput }) {
  switch (output.output_type) {
    case "summary":
      return <SummaryOutputView output={output} />;
    case "ranked":
      return <RankedOutputView output={output} />;
    case "draft":
      return <DraftOutputView output={output} />;
    case "review":
      return <ReviewOutputView output={output} />;
    case "workflow":
      return <WorkflowOutputView output={output} />;
    case "engine_list":
      return <EngineListOutputView output={output} />;
    case "market_list":
      return <MarketListOutputView output={output} />;
    case "program_list":
      return <ProgramListOutputView output={output} />;
    case "supplier_list":
      return <SupplierListOutputView output={output} />;
    case "executive_briefing":
      return <ExecutiveBriefingOutputView output={output} />;
    case "executive_action_queue":
      return <ExecutiveActionQueueOutputView output={output} />;
    case "executive_alerts":
      return <ExecutiveAlertsOutputView output={output} />;
    case "clarification":
      return <ClarificationOutputView output={output} />;
    case "unsupported":
      return <UnsupportedOutputView output={output} />;
  }
}
