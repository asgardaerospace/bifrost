// Type mirrors of backend Pydantic schemas.
// Keep field names snake_case to match the API wire format.

export type CommandClass = "read" | "analyze" | "draft" | "plan" | "execute" | "review";
export type CommandStatus = "completed" | "clarification_needed" | "unsupported" | "failed";

export interface EntityRef {
  entity_type: string;
  entity_id: number;
  label?: string | null;
}

export interface CommandClassification {
  command_class: CommandClass;
  intent: string;
  confidence: "high" | "medium" | "low";
  domain: "investor";
  referenced_entity?: EntityRef | null;
  matched_keywords: string[];
}

export interface StageCount {
  stage: string;
  count: number;
}

export interface OpportunitySummary {
  id: number;
  firm_id: number;
  firm_name?: string | null;
  stage: string;
  status: string;
  owner?: string | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
  fit_score?: number | null;
  probability_score?: number | null;
  strategic_value_score?: number | null;
  last_interaction_at?: string | null;
  days_since_last_interaction?: number | null;
  priority_score?: number | null;
}

export interface PrioritizedOpportunity {
  opportunity: OpportunitySummary;
  priority_score: number;
  rationale: string;
  recommended_next_action: string;
  factors: string[];
}

export interface AgentPipelineSummary {
  total_active: number;
  stage_counts: StageCount[];
  missing_next_step_count: number;
  overdue_follow_up_count: number;
  stale_count: number;
  stale_threshold_days: number;
  top_priority: OpportunitySummary[];
  overdue_follow_ups: OpportunitySummary[];
  stale_opportunities: OpportunitySummary[];
  narrative: string;
}

export interface TimelineHighlight {
  occurred_at: string;
  item_type: string;
  title: string;
  summary?: string | null;
}

export interface InvestorBrief {
  opportunity_id: number;
  firm_id: number;
  firm_name?: string | null;
  firm_overview?: string | null;
  primary_contact_id?: number | null;
  primary_contact_name?: string | null;
  primary_contact_email?: string | null;
  stage: string;
  status: string;
  owner?: string | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
  fit_score?: number | null;
  probability_score?: number | null;
  strategic_value_score?: number | null;
  last_interaction_at?: string | null;
  days_since_last_interaction?: number | null;
  blockers: string[];
  recent_activity: TimelineHighlight[];
  fit_assessment: string;
  strategic_value_assessment: string;
  recommended_executive_focus: string;
  missing_context: string[];
  generated_at: string;
}

export interface CommunicationRead {
  id: number;
  entity_type: string;
  entity_id: number;
  channel: string;
  direction: string;
  status: string;
  subject?: string | null;
  body?: string | null;
  from_address?: string | null;
  to_address?: string | null;
  sent_at?: string | null;
  source_system?: string | null;
  source_external_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FollowUpDraftResponse {
  communication: CommunicationRead;
  workflow_run: WorkflowRunRead;
}

export interface WorkflowRunRead {
  id: number;
  workflow_key: string;
  entity_type?: string | null;
  entity_id?: number | null;
  status: string;
  triggered_by?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  input_payload?: Record<string, unknown> | null;
  result_payload?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

// ---- investor engine (external, read-only) ----
export interface EngineContact {
  external_id: string;
  name: string;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  notes?: string | null;
}

export interface EngineActivity {
  external_id: string;
  kind: string;
  summary?: string | null;
  occurred_at?: string | null;
  author?: string | null;
}

export interface NormalizedInvestor {
  external_id: string;
  source: "investor_engine";
  firm_name: string;
  website?: string | null;
  stage_focus?: string | null;
  location?: string | null;
  description?: string | null;
  stage?: string | null;
  follow_up_status?: string | null;
  last_touch_at?: string | null;
  next_follow_up_at?: string | null;
  next_step?: string | null;
  owner?: string | null;
  amount?: string | null;
  target_close_date?: string | null;
  fit_score?: number | null;
  probability_score?: number | null;
  strategic_value_score?: number | null;
  contacts: EngineContact[];
  recent_activity: EngineActivity[];
  engine_updated_at?: string | null;
}

export interface EngineInvestorRow {
  external_id: string;
  firm_name: string;
  stage?: string | null;
  owner?: string | null;
  follow_up_status?: string | null;
  last_touch_at?: string | null;
  next_follow_up_at?: string | null;
  next_step?: string | null;
}

export interface ReviewItem {
  entity_type: string;
  entity_id: number;
  summary: string;
  status: string;
  link_hint?: string | null;
}

// ---- output variants ----
interface OutputBase<T extends string> {
  output_type: T;
  headline: string;
}

export interface SummaryOutput extends OutputBase<"summary"> {
  key_insights: string[];
  supporting_data: Record<string, unknown>;
  next_actions: string[];
  pipeline_summary?: AgentPipelineSummary | null;
  investor_brief?: InvestorBrief | null;
}

export interface RankedOutput extends OutputBase<"ranked"> {
  scoring_logic: string;
  items: PrioritizedOpportunity[];
  opportunities: OpportunitySummary[];
}

export interface DraftOutput extends OutputBase<"draft"> {
  communication: CommunicationRead;
  rationale: string;
  missing_context: string[];
  workflow_run?: WorkflowRunRead | null;
}

export interface WorkflowOutput extends OutputBase<"workflow"> {
  workflow_key: string;
  workflow_run: WorkflowRunRead;
  approval_required: boolean;
  actions_created: string[];
}

export interface ReviewOutput extends OutputBase<"review"> {
  pending_approvals: ReviewItem[];
  blocked_items: ReviewItem[];
}

export interface ClarificationOutput extends OutputBase<"clarification"> {
  message: string;
  candidates: EntityRef[];
  suggested_inputs: string[];
}

export interface UnsupportedOutput extends OutputBase<"unsupported"> {
  reason: string;
  supported_examples: string[];
}

export interface EngineListOutput extends OutputBase<"engine_list"> {
  source: "investor_engine";
  rationale?: string | null;
  investors: EngineInvestorRow[];
  counts: Record<string, number>;
}

export interface MarketAccountRow {
  id: number;
  name: string;
  sector?: string | null;
  region?: string | null;
  type?: string | null;
}

export interface MarketCampaignRow {
  id: number;
  name: string;
  sector?: string | null;
  region?: string | null;
  status: string;
}

export interface MarketOpportunityRow {
  id: number;
  account_id: number;
  account_name?: string | null;
  name: string;
  stage: string;
  sector?: string | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
  estimated_value?: number | null;
}

export interface MarketFollowUpRow {
  link_id: number;
  account_id: number;
  account_name?: string | null;
  campaign_id: number;
  campaign_name?: string | null;
  status: string;
  next_follow_up_at?: string | null;
  last_contacted_at?: string | null;
}

export interface ProgramRead {
  id: number;
  name: string;
  account_id: number;
  account_name?: string | null;
  description?: string | null;
  stage: "identified" | "pursuing" | "active" | "won" | "lost";
  estimated_value?: number | null;
  probability_score?: number | null;
  strategic_value_score?: number | null;
  owner?: string | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProgramStageCount {
  stage: string;
  count: number;
}

export interface ProgramPipelineSummary {
  total_programs: number;
  active_count: number;
  won_count: number;
  lost_count: number;
  stage_counts: ProgramStageCount[];
  high_value_count: number;
  high_value_threshold: number;
  overdue_count: number;
  total_estimated_value_active: number;
  high_value: ProgramRead[];
  overdue: ProgramRead[];
}

export interface ProgramRow {
  id: number;
  name: string;
  account_id: number;
  account_name?: string | null;
  stage: string;
  owner?: string | null;
  estimated_value?: number | null;
  probability_score?: number | null;
  strategic_value_score?: number | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
}

export interface ProgramStageBucket {
  stage: string;
  count: number;
}

// --- executive os ---

export type ExecDomain =
  | "capital"
  | "market"
  | "program"
  | "supplier"
  | "approval"
  | "engine";

export type AlertSeverity = "info" | "warn" | "critical";

export interface ActionItem {
  id: string;
  domain: ExecDomain;
  kind: string;
  title: string;
  description?: string | null;
  priority_score: number;
  due_at?: string | null;
  status?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: number | null;
  source_label: string;
  link_hint?: string | null;
}

export interface ActionQueue {
  generated_at: string;
  total: number;
  counts_by_domain: Record<string, number>;
  items: ActionItem[];
}

export interface Alert {
  id: string;
  severity: AlertSeverity;
  domain: ExecDomain;
  title: string;
  description: string;
  related_entity_type?: string | null;
  related_entity_id?: number | null;
  recommended_action: string;
  link_hint?: string | null;
}

export interface AlertBundle {
  generated_at: string;
  total: number;
  counts_by_severity: Record<string, number>;
  alerts: Alert[];
}

export interface BriefingItem {
  label: string;
  subtitle?: string | null;
  badge?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: number | null;
  link_hint?: string | null;
}

export interface BriefingSection {
  domain: ExecDomain;
  title: string;
  headline: string;
  count: number;
  items: BriefingItem[];
}

export interface ExecutiveMetrics {
  capital_active: number;
  capital_overdue: number;
  capital_stale: number;
  capital_pending_approvals: number;
  market_accounts: number;
  market_active_campaigns: number;
  market_active_opportunities: number;
  market_follow_ups_due: number;
  programs_active: number;
  programs_high_value: number;
  programs_overdue: number;
  suppliers_total: number;
  suppliers_qualified: number;
  suppliers_onboarded: number;
  engine_writes_pending: number;
  engine_writes_failed: number;
}

export interface DailyBriefing {
  generated_at: string;
  headline: string;
  narrative: string[];
  metrics: ExecutiveMetrics;
  sections: BriefingSection[];
  top_actions: ActionItem[];
  top_risks: Alert[];
}

export interface ExecutiveBriefingOutput
  extends OutputBase<"executive_briefing"> {
  briefing: DailyBriefing;
}

export interface ExecutiveActionQueueOutput
  extends OutputBase<"executive_action_queue"> {
  queue: ActionQueue;
}

export interface ExecutiveAlertsOutput
  extends OutputBase<"executive_alerts"> {
  alerts: AlertBundle;
}

export interface SupplierRead {
  id: number;
  name: string;
  type?: string | null;
  region?: string | null;
  country?: string | null;
  website?: string | null;
  notes?: string | null;
  onboarding_status:
    | "identified"
    | "contacted"
    | "qualified"
    | "onboarded";
  preferred_partner_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierCapabilityRead {
  id: number;
  supplier_id: number;
  capability_type: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierCertificationRead {
  id: number;
  supplier_id: number;
  certification: string;
  status: "active" | "pending" | "expired";
  expiration_date?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProgramSupplierRead {
  id: number;
  program_id: number;
  program_name?: string | null;
  supplier_id: number;
  supplier_name?: string | null;
  role: "primary" | "secondary" | "backup";
  status: "proposed" | "engaged" | "confirmed";
  created_at: string;
  updated_at: string;
}

export interface OnboardingPipelineSummary {
  total: number;
  by_status: Record<string, number>;
  qualified: number;
  onboarded: number;
  active_program_supplier_count: number;
}

export interface SupplierRow {
  id: number;
  name: string;
  type?: string | null;
  region?: string | null;
  country?: string | null;
  onboarding_status: string;
  preferred_partner_score?: number | null;
  capabilities: string[];
  certifications: string[];
}

export interface ProgramSupplierRow {
  link_id: number;
  program_id: number;
  program_name?: string | null;
  supplier_id: number;
  supplier_name?: string | null;
  role: string;
  status: string;
}

export interface SupplierListOutput extends OutputBase<"supplier_list"> {
  kind:
    | "all"
    | "qualified"
    | "by_capability"
    | "by_region"
    | "for_program"
    | "onboarding";
  rationale?: string | null;
  suppliers: SupplierRow[];
  program_links: ProgramSupplierRow[];
  by_capability: Record<string, SupplierRow[]>;
  by_region: Record<string, SupplierRow[]>;
  counts: Record<string, number>;
}

export interface ProgramListOutput extends OutputBase<"program_list"> {
  kind: "active" | "high_value" | "overdue" | "by_stage" | "pipeline";
  rationale?: string | null;
  programs: ProgramRow[];
  stage_counts: ProgramStageBucket[];
  counts: Record<string, number>;
  totals: Record<string, number>;
}

export interface MarketListOutput extends OutputBase<"market_list"> {
  kind: "accounts" | "campaigns" | "opportunities" | "follow_ups" | "by_sector";
  rationale?: string | null;
  accounts: MarketAccountRow[];
  campaigns: MarketCampaignRow[];
  opportunities: MarketOpportunityRow[];
  follow_ups: MarketFollowUpRow[];
  counts: Record<string, number>;
  by_sector: Record<string, MarketOpportunityRow[]>;
}

export type CommandOutput =
  | SummaryOutput
  | RankedOutput
  | DraftOutput
  | WorkflowOutput
  | ReviewOutput
  | EngineListOutput
  | MarketListOutput
  | ProgramListOutput
  | SupplierListOutput
  | ExecutiveBriefingOutput
  | ExecutiveActionQueueOutput
  | ExecutiveAlertsOutput
  | ClarificationOutput
  | UnsupportedOutput;

export interface CommandRequest {
  text: string;
  actor?: string;
  context_entity?: EntityRef;
}

export interface CommandResponse {
  command_text: string;
  normalized_text: string;
  classification: CommandClassification;
  status: CommandStatus;
  output: CommandOutput;
  records_created: EntityRef[];
  duration_ms: number;
  executed_at: string;
  history_id?: number | null;
}

export interface CommandHistoryItem {
  id: number;
  command_text: string;
  normalized_text?: string | null;
  command_class?: string | null;
  referenced_entity_type?: string | null;
  referenced_entity_id?: number | null;
  output_type?: string | null;
  records_created: boolean;
  status?: string | null;
  duration_ms?: number | null;
  actor?: string | null;
  created_at: string;
}

export interface ApprovalRead {
  id: number;
  entity_type: string;
  entity_id: number;
  workflow_run_id?: number | null;
  action: string;
  status: string;
  requested_by?: string | null;
  reviewer?: string | null;
  reviewed_at?: string | null;
  decision_note?: string | null;
  communication_subject?: string | null;
  communication_status?: string | null;
  source_system?: string | null;
  source_external_id?: string | null;
  created_at: string;
  updated_at: string;
}

// --- market os ---

export interface MarketDashboardSummary {
  total_accounts: number;
  active_campaigns: number;
  active_opportunities: number;
  accounts_needing_follow_up: number;
}

export interface AccountRead {
  id: number;
  name: string;
  sector?: string | null;
  region?: string | null;
  type?: string | null;
  website?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignRead {
  id: number;
  name: string;
  sector?: string | null;
  region?: string | null;
  description?: string | null;
  status: "active" | "paused" | "completed";
  created_at: string;
  updated_at: string;
}

export interface MarketOpportunityRead {
  id: number;
  account_id: number;
  account_name?: string | null;
  name: string;
  description?: string | null;
  stage: "identified" | "exploring" | "active" | "closed";
  estimated_value?: number | null;
  next_step?: string | null;
  next_step_due_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountCampaignRead {
  id: number;
  account_id: number;
  account_name?: string | null;
  campaign_id: number;
  campaign_name?: string | null;
  status: "not_contacted" | "contacted" | "responded" | "engaged";
  last_contacted_at?: string | null;
  next_follow_up_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type EngineWriteAction =
  | "update_follow_up"
  | "log_touch"
  | "update_stage";

export type EngineWriteStatus =
  | "pending"
  | "processing"
  | "succeeded"
  | "failed";

export interface PendingEngineWriteRead {
  id: number;
  external_id: string;
  action_type: string;
  payload_json: Record<string, unknown>;
  status: EngineWriteStatus;
  attempt_count: number;
  last_error?: string | null;
  idempotency_key: string;
  engine_updated_at_snapshot?: string | null;
  approval_id?: number | null;
  requested_by?: string | null;
  executed_at?: string | null;
  created_at: string;
  updated_at: string;
}

// ----- Intelligence OS -----

export type IntelCategory =
  | "vc_funding"
  | "defense_tech"
  | "space_systems"
  | "aerospace_manufacturing"
  | "supply_chain"
  | "policy_procurement"
  | "competitor_move"
  | "partner_signal"
  | "supplier_signal"
  | "uncategorized";

export type IntelActionStatus =
  | "pending"
  | "acknowledged"
  | "resolved"
  | "dismissed";

export interface IntelEntityRead {
  id: number;
  intel_item_id: number;
  entity_type: string;
  entity_name: string;
  entity_id?: number | null;
  role?: string | null;
  created_at: string;
}

export interface IntelTagRead {
  id: number;
  intel_item_id: number;
  tag: string;
  created_at: string;
}

export interface IntelActionRead {
  id: number;
  intel_item_id: number;
  action_type: string;
  recommended_action: string;
  status: IntelActionStatus;
  created_at: string;
  updated_at: string;
}

export interface IntelItemRead {
  id: number;
  source: string;
  title: string;
  url?: string | null;
  published_at?: string | null;
  region?: string | null;
  category: IntelCategory;
  summary?: string | null;
  strategic_relevance_score: number;
  urgency_score: number;
  confidence_score: number;
  created_at: string;
  updated_at: string;
  entities: IntelEntityRead[];
  tags: IntelTagRead[];
  actions: IntelActionRead[];
}

export interface IntelTopSignals {
  generated_at: string;
  total: number;
  items: IntelItemRead[];
}

export interface IntelCategoryBucket {
  category: IntelCategory;
  count: number;
  items: IntelItemRead[];
}

export interface IntelByCategory {
  generated_at: string;
  total: number;
  categories: IntelCategoryBucket[];
}

export interface IntelRegionBucket {
  region: string;
  count: number;
  items: IntelItemRead[];
}

export interface IntelByRegion {
  generated_at: string;
  total: number;
  regions: IntelRegionBucket[];
}

export interface IntelIngestionReport {
  started_at: string;
  finished_at: string;
  provider_counts: Record<string, number>;
  created: number;
  updated: number;
  skipped: number;
  total_items_seen: number;
}

export interface ActivityEventRead {
  id: number;
  entity_type: string;
  entity_id: number;
  event_type: string;
  actor?: string | null;
  source?: string | null;
  payload?: Record<string, unknown> | null;
  created_at: string;
}
