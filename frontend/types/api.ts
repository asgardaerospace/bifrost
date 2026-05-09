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

// =============================================================================
// Sprint 0 — canonical operational core (mission, execution, events, graph).
// Mirrors backend/app/schemas/{mission,execution,operational_event,relationship}.py.
// =============================================================================

export type MissionStatus = "planning" | "active" | "paused" | "completed" | "cancelled";
export type MissionPriority = "low" | "normal" | "high" | "critical";
export type MissionHealth = "nominal" | "watch" | "strain" | "critical";

export interface MissionRead {
  id: number;
  codename: string;
  name: string;
  description?: string | null;
  mission_type: string;
  status: MissionStatus;
  priority: MissionPriority;
  pressure_score: number;
  health_status: MissionHealth;
  owner_user_id?: number | null;
  parent_mission_id?: number | null;
  starts_at?: string | null;
  target_completion_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MissionCreate {
  codename: string;
  name: string;
  description?: string | null;
  mission_type?: string;
  status?: MissionStatus;
  priority?: MissionPriority;
  pressure_score?: number;
  health_status?: MissionHealth;
  owner_user_id?: number | null;
  parent_mission_id?: number | null;
  starts_at?: string | null;
  target_completion_at?: string | null;
}

export interface MissionUpdate {
  name?: string;
  description?: string | null;
  mission_type?: string;
  status?: MissionStatus;
  priority?: MissionPriority;
  pressure_score?: number;
  health_status?: MissionHealth;
  owner_user_id?: number | null;
  parent_mission_id?: number | null;
  starts_at?: string | null;
  target_completion_at?: string | null;
  completed_at?: string | null;
}

export interface MissionEntityRead {
  id: number;
  mission_id: number;
  entity_type: string;
  entity_id: number;
  relationship_type: string;
  weight: number;
  notes?: string | null;
  created_at: string;
}

export interface MissionEntityCreate {
  entity_type: string;
  entity_id: number;
  relationship_type?: string;
  weight?: number;
  notes?: string | null;
}

export interface MissionPressure {
  mission_id: number;
  pressure_score: number;
  health_status: MissionHealth;
  components: Record<string, number>;
  blockers_count: number;
  overdue_count: number;
  pending_approvals_count: number;
  explanation: string;
}

export interface MissionDependencyEdge {
  relationship_type: string;
  other_mission_id: number;
  other_codename?: string | null;
  other_name?: string | null;
  direction: "upstream" | "downstream";
}

export interface MissionDependencies {
  mission_id: number;
  upstream: MissionDependencyEdge[];
  downstream: MissionDependencyEdge[];
}

export interface MissionTimelineItem {
  item_type: string;
  item_id: number;
  occurred_at: string;
  title: string;
  summary?: string | null;
  actor?: string | null;
  entity_type?: string | null;
  entity_id?: number | null;
  data?: Record<string, unknown> | null;
}

export interface MissionTimeline {
  mission_id: number;
  count: number;
  items: MissionTimelineItem[];
}

// --- Execution queue ---------------------------------------------------------

export type QueueItemStatus =
  | "queued"
  | "in_progress"
  | "blocked"
  | "completed"
  | "cancelled"
  | "deferred";

export type QueueItemType =
  | "task"
  | "approval"
  | "draft"
  | "followup"
  | "recommendation"
  | "mission_action"
  | "blocker";

export interface ExecutionQueueItemRead {
  id?: number | null;
  item_type: QueueItemType;
  source_type?: string | null;
  source_id?: number | null;
  mission_id?: number | null;
  title: string;
  summary?: string | null;
  status: QueueItemStatus;
  priority_score: number;
  pressure_score: number;
  owner?: string | null;
  due_at?: string | null;
  blocked_reason?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  is_projected: boolean;
  meta?: Record<string, unknown> | null;
}

export interface ExecutionQueue {
  count: number;
  items: ExecutionQueueItemRead[];
}

export interface ExecutionQueueItemCreate {
  item_type: QueueItemType;
  source_type?: string | null;
  source_id?: number | null;
  mission_id?: number | null;
  title: string;
  summary?: string | null;
  priority_score?: number;
  pressure_score?: number;
  owner?: string | null;
  due_at?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface ExecutionQueueItemUpdate {
  status?: QueueItemStatus;
  priority_score?: number;
  pressure_score?: number;
  owner?: string | null;
  due_at?: string | null;
  blocked_reason?: string | null;
  completed_at?: string | null;
  meta?: Record<string, unknown> | null;
}

// --- Operational events ------------------------------------------------------

export type EventSeverity = "info" | "notice" | "warning" | "critical";

export interface OperationalEventRead {
  id: number;
  topic: string;
  event_type: string;
  mission_id?: number | null;
  entity_type?: string | null;
  entity_id?: number | null;
  actor?: string | null;
  source?: string | null;
  severity: EventSeverity;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface OperationalEventStream {
  count: number;
  cursor?: number | null;
  items: OperationalEventRead[];
}

export interface OperationalEventCreate {
  topic: string;
  event_type: string;
  mission_id?: number | null;
  entity_type?: string | null;
  entity_id?: number | null;
  actor?: string | null;
  source?: string | null;
  severity?: EventSeverity;
  payload?: Record<string, unknown> | null;
}

// --- Relationships / propagation --------------------------------------------

export type RelationshipType =
  | "depends_on"
  | "blocks"
  | "supports"
  | "funds"
  | "supplies"
  | "owns"
  | "affects"
  | "influences"
  | "participates_in"
  | "relates_to"
  | "mitigates"
  | "escalates_to"
  | "connected_to";

export interface RelationshipRead {
  id: number;
  source_type: string;
  source_id: number;
  target_type: string;
  target_id: number;
  relationship_type: RelationshipType;
  weight: number;
  meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RelationshipCreate {
  source_type: string;
  source_id: number;
  target_type: string;
  target_id: number;
  relationship_type: RelationshipType;
  weight?: number;
  meta?: Record<string, unknown> | null;
}

export interface PropagationNode {
  entity_type: string;
  entity_id: number;
  distance: number;
  path: RelationshipType[];
}

export interface PropagationView {
  source_type: string;
  source_id: number;
  direction: "downstream" | "upstream" | "both";
  depth: number;
  nodes: PropagationNode[];
}

// =============================================================================
// Sprint 1 — auth
// =============================================================================

export interface UserRead {
  id: number;
  email: string;
  name?: string | null;
  status: string;
  primary_role: string;
  has_password: boolean;
  created_at: string;
  updated_at: string;
}

export interface CurrentUserRead {
  id: number;
  email: string;
  name?: string | null;
  primary_role: string;
  is_anonymous: boolean;
}

export interface LoginRequest {
  email: string;
  password?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserRead;
}

export interface UserCreate {
  email: string;
  name?: string | null;
  primary_role?: string;
  password?: string | null;
}

// =============================================================================
// Sprint 2 — pressure history + presence + websocket payloads
// =============================================================================

export interface PressureSnapshotRead {
  id: number;
  mission_id: number;
  score: number;
  health_status: MissionHealth;
  components: Record<string, number>;
  blockers_count: number;
  overdue_count: number;
  pending_approvals_count: number;
  unresolved_dependencies_count: number;
  high_priority_intel_count: number;
  activity_volume: number;
  escalation_flags_count: number;
  source: string;
  trigger_event_id?: number | null;
  computed_at: string;
}

export interface PressureHistory {
  mission_id: number;
  count: number;
  snapshots: PressureSnapshotRead[];
}

export interface PresenceSessionRead {
  id: number;
  client_id: string;
  user_id?: number | null;
  display_name?: string | null;
  mission_id?: number | null;
  connected_at: string;
  last_heartbeat: string;
  disconnected_at?: string | null;
}

export interface PresenceList {
  count: number;
  operators: PresenceSessionRead[];
}

// =============================================================================
// Sprint 5 — cognition + recommendations + simulation + drafting
// =============================================================================

export interface CognitionCommandRequest {
  command: string;
  mission_id?: number | null;
}

export interface CognitionResponseRead {
  command: string;
  intent_id?: string | null;
  intent_label?: string | null;
  matched_keywords: string[];
  intent_confidence: number;
  synthesis: SynthesisResponseRead;
}

export interface IntentDescriptor {
  intent_id: string;
  label: string;
  keywords: string[];
  requires_mission: boolean;
  temporal_hours?: number | null;
}

export interface RecommendationRead {
  id: number;
  recommendation_type: string;
  title: string;
  rationale: string;
  confidence: number;
  mission_id?: number | null;
  target_entity_type?: string | null;
  target_entity_id?: number | null;
  projected_impact?: string | null;
  projected_delta?: number | null;
  components: Record<string, unknown>;
  citations?: Array<Record<string, unknown>> | null;
  source: string;
  created_by?: string | null;
  status: string;
  decided_by?: string | null;
  decided_at?: string | null;
  decision_note?: string | null;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecommendationDecision {
  decision: "accepted" | "dismissed";
  decided_by: string;
  decision_note?: string | null;
}

export interface RecommendationGenerationReport {
  created: number;
  refreshed: number;
  total_pending: number;
}

export interface ImpactedMissionRead {
  mission_id: number;
  codename: string;
  name: string;
  pressure_delta: number;
  rationale: string;
}

export interface PropagationEdgeRead {
  source_type: string;
  source_id: number;
  target_type: string;
  target_id: number;
  relationship_type: string;
  distance: number;
}

export interface SimulationResultRead {
  simulation_type: string;
  seed: Record<string, unknown>;
  impacted_missions: ImpactedMissionRead[];
  propagation_paths: PropagationEdgeRead[];
  pressure_deltas: Record<string, number>;
  confidence: number;
  assumptions: string[];
  notes: string[];
}

// =============================================================================
// Sprint 4 — aerospace intelligence signals + relevance + impact
// =============================================================================

export type SignalType =
  | "funding"
  | "procurement"
  | "supplier_risk"
  | "manufacturing"
  | "launch"
  | "geopolitical"
  | "regulatory"
  | "defense"
  | "partnership"
  | "acquisition"
  | "market_shift";

export interface SignalSummaryRead {
  id: number;
  source: string;
  title: string;
  url?: string | null;
  region?: string | null;
  category: string;
  summary?: string | null;
  published_at?: string | null;
  strategic_relevance_score: number;
  urgency_score: number;
  confidence_score: number;
  signal_type: SignalType;
  severity: "info" | "notice" | "warning" | "critical";
}

export interface SignalRelevanceRead {
  id: number;
  intel_item_id: number;
  mission_id: number;
  score: number;
  decayed_score: number;
  components: Record<string, unknown>;
  is_relevant: boolean;
  expires_at?: string | null;
  computed_at: string;
  created_at: string;
  updated_at: string;
}

export interface SignalImpactRead {
  id: number;
  intel_item_id: number;
  mission_id: number;
  impact_type: string;
  contribution: number;
  components: Record<string, unknown>;
  notes?: string | null;
  expires_at?: string | null;
  computed_at: string;
  created_at: string;
  updated_at: string;
}

export interface MissionSignalRead {
  relevance: SignalRelevanceRead;
  signal: SignalSummaryRead;
  impact_type?: string | null;
  contribution?: number | null;
}

export interface MissionSignalsResponse {
  mission_id: number;
  count: number;
  items: MissionSignalRead[];
}

export interface IngestionReportRead {
  ingested: number;
  deduped: number;
  relevance_rows: number;
  impact_rows: number;
  affected_missions: number;
}

// =============================================================================
// Sprint 3 — memory + retrieval + RAG synthesis
// =============================================================================

export interface MemoryRecordRead {
  id: number;
  source_type: string;
  source_id: number;
  source_hash: string;
  title?: string | null;
  content: string;
  mission_id?: number | null;
  entity_type?: string | null;
  entity_id?: number | null;
  created_by?: string | null;
  source_occurred_at?: string | null;
  version: number;
  embedding_status: string;
  embedded_at?: string | null;
  token_count: number;
  meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface RetrievalScoreComponents {
  semantic: number;
  keyword: number;
  recency: number;
  w_semantic: number;
  w_keyword: number;
  w_recency: number;
}

export interface RetrievalResultRead {
  chunk_id: number;
  record_id: number;
  source_type: string;
  source_id: number;
  title?: string | null;
  text: string;
  score: number;
  components: RetrievalScoreComponents;
  mission_id?: number | null;
  entity_type?: string | null;
  entity_id?: number | null;
  occurred_at?: string | null;
  chunk_index: number;
  embedding_model?: string | null;
}

export interface RetrievalTraceRead {
  query: string;
  candidates_considered: number;
  chunks_returned: number;
  scoped_mission_id?: number | null;
  scoped_entity_type?: string | null;
  scoped_entity_id?: number | null;
  since?: string | null;
  embedding_model: string;
  weights: Record<string, number>;
}

export interface SearchQuery {
  query: string;
  mission_id?: number | null;
  entity_type?: string | null;
  entity_id?: number | null;
  since?: string | null;
  source_types?: string[] | null;
  limit?: number;
}

export interface SearchResponse {
  results: RetrievalResultRead[];
  trace: RetrievalTraceRead;
}

export interface CitationRead {
  marker: string;
  chunk_id: number;
  record_id: number;
  source_type: string;
  source_id: number;
  title?: string | null;
  excerpt: string;
}

export interface SynthesisResponseRead {
  objective: string;
  summary: string;
  confidence: number;
  weak_retrieval: boolean;
  citations: CitationRead[];
  retrieval_trace: RetrievalTraceRead;
  model: string;
}

export interface RelatedMissionRead {
  mission_id: number;
  title?: string | null;
  score: number;
  components: RetrievalScoreComponents;
  excerpt: string;
}

export interface RelatedMissionsResponse {
  related: RelatedMissionRead[];
  trace: RetrievalTraceRead;
}

// =============================================================================
// Sprint 6 — governed autonomous coordination (agents + workflow trace)
// =============================================================================

export interface AgentDescriptorRead {
  name: string;
  version: string;
  purpose: string;
  allowed_actions: string[];
  required_approvals: string[];
  accessible_domains: string[];
  confidence_threshold: number;
  workflow_key: string;
  stages: string[];
  escalation_rules: string[];
}

export interface AgentRunRequest {
  trigger?: string;
  mission_id?: number | null;
  propagate_handoffs?: boolean;
}

export interface AgentRunReport {
  operation_id: number;
  agent_name: string;
  workflow_key: string;
  final_status: "proposed" | "weak" | "failed" | "cancelled" | string;
  confidence: number;
  stage_count: number;
  proposed_action_count: number;
  error?: string | null;
  handoff_runs: number[];
}

export interface AutonomyOperationRead {
  id: number;
  agent_name: string;
  operation_type: string;
  mission_id?: number | null;
  status: string;
  confidence_score: number;
  reasoning?: string | null;
  retrieval_citations?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
  proposed_at: string;
  decided_at?: string | null;
  executed_at?: string | null;
  decided_by_user_id?: number | null;
  trigger?: string | null;
  workflow_key?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentWorkflowStageRead {
  id: number;
  autonomy_operation_id: number;
  stage_index: number;
  stage_name: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  input_payload?: Record<string, unknown> | null;
  output_payload?: Record<string, unknown> | null;
  retrieval_trace?: Record<string, unknown> | null;
  confidence?: number | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTraceRead {
  operation: AutonomyOperationRead;
  stages: AgentWorkflowStageRead[];
  proposed_action_count: number;
}

export interface ProposedActionRead {
  id: number;
  autonomy_operation_id: number;
  action_type: string;
  target_entity_type?: string | null;
  target_entity_id?: number | null;
  payload?: Record<string, unknown> | null;
  status: string;
  requires_approval: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProposedActionDecision {
  decision: "approved" | "rejected";
  decided_by?: string | null;
  note?: string | null;
}

// ===== Sprint 7 — horizon, topology, operational timeline, environment =====

export type HorizonBand = "nominal" | "watch" | "strain" | "critical";

export interface HorizonMissionPulse {
  mission_id: number;
  codename: string;
  name: string;
  priority: string;
  health_status: HorizonBand;
  pressure_score: number;
  pressure_delta_24h: number;
  blockers: number;
  overdue: number;
  pending_approvals: number;
  open_proposed_actions: number;
  last_event_at: string | null;
}

export interface HorizonEscalation {
  id: string;
  severity: "info" | "warn" | "critical";
  domain: string;
  title: string;
  detail: string;
  mission_id?: number | null;
  mission_codename?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: number | null;
  link_hint?: string | null;
}

export interface HorizonOpportunity {
  id: string;
  domain: string;
  title: string;
  detail: string;
  confidence: number;
  related_entity_type?: string | null;
  related_entity_id?: number | null;
  link_hint?: string | null;
}

export interface HorizonTempo {
  events_last_hour: number;
  events_last_24h: number;
  approvals_decided_24h: number;
  proposed_actions_decided_24h: number;
  agent_runs_24h: number;
  workflows_completed_24h: number;
}

export interface HorizonPressureMap {
  nominal: number;
  watch: number;
  strain: number;
  critical: number;
  average_score: number;
  peak_score: number;
  peak_mission_id?: number | null;
  peak_mission_codename?: string | null;
}

export interface HorizonView {
  generated_at: string;
  headline: string;
  band: HorizonBand;
  pressure_map: HorizonPressureMap;
  tempo: HorizonTempo;
  top_missions: HorizonMissionPulse[];
  escalations: HorizonEscalation[];
  opportunities: HorizonOpportunity[];
  narrative: string[];
}

export type TopologyNodeKind =
  | "mission"
  | "supplier"
  | "program"
  | "investor_firm"
  | "account"
  | "intel_item"
  | "agent";

export interface TopologyNode {
  id: string;
  kind: TopologyNodeKind;
  entity_id: number;
  label: string;
  sublabel?: string | null;
  band: HorizonBand;
  pressure_score: number;
  cluster?: string | null;
  weight: number;
  meta: Record<string, unknown>;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  weight: number;
  propagation: "upstream" | "downstream" | "lateral";
  intensity: number;
  meta: Record<string, unknown>;
}

export interface PropagationPath {
  origin: string;
  terminal: string;
  intensity: number;
  band: HorizonBand;
  path: string[];
  edge_kinds: string[];
  explanation: string;
}

export interface TopologyView {
  generated_at: string;
  scope: "org" | "mission";
  mission_id?: number | null;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  propagation_paths: PropagationPath[];
  cluster_summary: Record<string, number>;
}

export type OperationalTimelineKind =
  | "operational_event"
  | "approval_decided"
  | "proposed_action"
  | "agent_run"
  | "recommendation"
  | "escalation"
  | "pressure_shift"
  | "workflow_stage";

export interface OperationalTimelineEntry {
  id: string;
  kind: OperationalTimelineKind;
  occurred_at: string;
  title: string;
  summary?: string | null;
  severity: "info" | "notice" | "warn" | "critical";
  actor?: string | null;
  mission_id?: number | null;
  mission_codename?: string | null;
  entity_type?: string | null;
  entity_id?: number | null;
  cluster_id?: string | null;
  causal_parent_id?: string | null;
  propagation: string[];
  data: Record<string, unknown>;
}

export interface OperationalTimelineCluster {
  id: string;
  label: string;
  started_at: string;
  ended_at: string;
  entry_count: number;
  severity: "info" | "notice" | "warn" | "critical";
  mission_ids: number[];
  summary?: string | null;
}

export interface OperationalTimelineView {
  generated_at: string;
  scope: "org" | "mission";
  mission_id?: number | null;
  window_started_at: string;
  window_ended_at: string;
  count: number;
  counts_by_kind: Record<string, number>;
  counts_by_severity: Record<string, number>;
  entries: OperationalTimelineEntry[];
  clusters: OperationalTimelineCluster[];
}

export type EnvironmentBand = "calm" | "active" | "elevated" | "critical";

export interface EnvironmentPulse {
  generated_at: string;
  band: EnvironmentBand;
  pressure_index: number;
  propagation_index: number;
  activity_rate: number;
  escalation_count: number;
  open_proposed_actions: number;
  active_agent_runs: number;
  presence_count: number;
  realtime_subscribers: number;
}

export interface EnvironmentTrend {
  pulses: EnvironmentPulse[];
  pressure_delta: number;
  propagation_delta: number;
  activity_delta: number;
}

export interface EnvironmentSnapshot {
  pulse: EnvironmentPulse;
  trend: EnvironmentTrend;
  narrative: string[];
}

// Server → client websocket frames (subset).
export type WSFrame =
  | { type: "hello"; client_id: string }
  | { type: "subscribed"; topic: string; mission_id: number | null }
  | { type: "pong"; ts: string }
  | { type: "presence_changed"; topic: "presence"; mission_id: number | null; client_id: string }
  | { type: "error"; detail: string }
  | {
      type: "event";
      topic: string;
      event_type: string;
      id: number;
      mission_id: number | null;
      entity_type: string | null;
      entity_id: number | null;
      actor: string | null;
      source: string | null;
      severity: EventSeverity;
      payload?: Record<string, unknown> | null;
      occurred_at: string | null;
    };
