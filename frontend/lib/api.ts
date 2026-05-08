import type {
  ActivityEventRead,
  AgentPipelineSummary,
  AccountCampaignRead,
  AccountRead,
  ApprovalRead,
  CampaignRead,
  CommandHistoryItem,
  MarketDashboardSummary,
  MarketOpportunityRead,
  PendingEngineWriteRead,
  ActionQueue,
  AlertBundle,
  DailyBriefing,
  OnboardingPipelineSummary,
  ProgramPipelineSummary,
  ProgramRead,
  ProgramSupplierRead,
  SupplierRead,
  CommandRequest,
  CommandResponse,
  FollowUpDraftResponse,
  NormalizedInvestor,
  OpportunitySummary,
  IntelActionRead,
  IntelByCategory,
  IntelByRegion,
  IntelIngestionReport,
  IntelItemRead,
  IntelTopSignals,
  // Sprint 0 — canonical operational core
  ExecutionQueue,
  ExecutionQueueItemCreate,
  ExecutionQueueItemRead,
  ExecutionQueueItemUpdate,
  MissionCreate,
  MissionDependencies,
  MissionEntityCreate,
  MissionEntityRead,
  MissionPressure,
  MissionRead,
  MissionTimeline,
  MissionUpdate,
  OperationalEventCreate,
  OperationalEventRead,
  OperationalEventStream,
  PropagationView,
  RelationshipCreate,
  RelationshipRead,
  // Sprint 1 — auth
  CurrentUserRead,
  LoginRequest,
  TokenResponse,
  UserCreate,
  UserRead,
  // Sprint 2 — pressure history + presence
  PressureHistory,
  PressureSnapshotRead,
  PresenceList,
  // Sprint 3 — memory + retrieval + RAG
  MemoryRecordRead,
  RelatedMissionsResponse,
  SearchQuery,
  SearchResponse,
  SynthesisResponseRead,
  // Sprint 4 — intelligence signals + relevance + executive brief
  IngestionReportRead,
  MissionSignalsResponse,
  SignalImpactRead,
  SignalRelevanceRead,
  SignalSummaryRead,
  // Sprint 5 — cognition + recommendations + simulation
  CognitionCommandRequest,
  CognitionResponseRead,
  IntentDescriptor,
  RecommendationDecision,
  RecommendationGenerationReport,
  RecommendationRead,
  SimulationResultRead,
} from "@/types/api";

export interface EngineDraftRequest {
  subject?: string;
  body?: string;
  from_address?: string;
  to_address?: string;
  actor?: string;
}

// Normalize the configured base URL:
//  - strip trailing slashes so `${BASE_URL}${path}` never double-slashes
//  - fall back to dev default only outside production builds
const RAW_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000/api/v1");

export const API_BASE_URL = RAW_BASE.replace(/\/+$/, "");
export const API_BASE_URL_MISSING = API_BASE_URL === "";

class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  if (API_BASE_URL_MISSING) {
    throw new ApiError(
      0,
      null,
      "API base URL is not configured. Set NEXT_PUBLIC_API_BASE_URL."
    );
  }

  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError(
      0,
      null,
      `Network error contacting API (${e instanceof Error ? e.message : "fetch failed"})`
    );
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = null;
      }
    }
    const msg =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, msg);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// ----- minimal firm / opportunity types for create forms -----
export interface FirmRead {
  id: number;
  name: string;
  website?: string | null;
  stage_focus?: string | null;
  location?: string | null;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FirmCreate {
  name: string;
  stage_focus?: string | null;
  description?: string | null;
}

export interface OpportunityCreate {
  firm_id: number;
  stage: string;
  next_step?: string | null;
  next_step_due_at?: string | null;
}

export interface OpportunityRead extends OpportunityCreate {
  id: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export const api = {
  submitCommand: (payload: CommandRequest) =>
    request<CommandResponse>("/command-console/commands", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  commandHistory: (limit = 25) =>
    request<CommandHistoryItem[]>(`/command-console/history?limit=${limit}`),

  pipelineSummary: () =>
    request<AgentPipelineSummary>(`/investor-agent/pipeline-summary`),

  overdue: () =>
    request<OpportunitySummary[]>(
      `/investors/opportunities/pipeline/overdue`
    ),

  stale: (thresholdDays = 21) =>
    request<OpportunitySummary[]>(
      `/investors/opportunities/pipeline/stale?threshold_days=${thresholdDays}`
    ),

  pendingApprovals: () =>
    request<ApprovalRead[]>(`/approvals/?status=pending`),

  listApprovals: (status?: string, limit = 100) => {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    qs.set("limit", String(limit));
    return request<ApprovalRead[]>(`/approvals/?${qs.toString()}`);
  },

  activity: (limit = 25) =>
    request<ActivityEventRead[]>(`/activity/?limit=${limit}`),

  listFirms: (limit = 200) =>
    request<FirmRead[]>(`/investors/firms?limit=${limit}`),

  createFirm: (payload: FirmCreate) =>
    request<FirmRead>("/investors/firms", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createOpportunity: (payload: OpportunityCreate) =>
    request<OpportunityRead>("/investors/opportunities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- investor engine (external, read-only) ---
  engineList: (params: {
    stage?: string;
    follow_up_status?: string;
    owner?: string;
    skip?: number;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.stage) qs.set("stage", params.stage);
    if (params.follow_up_status)
      qs.set("follow_up_status", params.follow_up_status);
    if (params.owner) qs.set("owner", params.owner);
    qs.set("skip", String(params.skip ?? 0));
    qs.set("limit", String(params.limit ?? 100));
    return request<NormalizedInvestor[]>(
      `/investor-engine/investors?${qs.toString()}`
    );
  },

  engineGet: (externalId: string) =>
    request<NormalizedInvestor>(
      `/investor-engine/investors/${encodeURIComponent(externalId)}`
    ),

  engineFollowUpsDue: (limit = 50) =>
    request<NormalizedInvestor[]>(
      `/investor-engine/follow-ups/due?limit=${limit}`
    ),

  engineDashboardSummary: () =>
    request<Record<string, number>>(`/investor-engine/dashboard/summary`),

  engineSync: () =>
    request<Record<string, number>>(`/investor-engine/sync`, {
      method: "POST",
    }),

  engineCreateFollowUpDraft: (
    externalId: string,
    payload: EngineDraftRequest = {},
  ) =>
    request<FollowUpDraftResponse>(
      `/investor-engine/investors/${encodeURIComponent(externalId)}/follow-up-draft`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  requestSendApproval: (
    communicationId: number,
    payload: { requested_by?: string; note?: string } = {},
  ) =>
    request<ApprovalRead>(
      `/communications/${communicationId}/request-send-approval`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  approveApproval: (
    approvalId: number,
    payload: { reviewer: string; decision_note?: string },
  ) =>
    request<ApprovalRead>(`/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- market os ---
  marketDashboardSummary: () =>
    request<MarketDashboardSummary>(`/market/dashboard/summary`),

  listAccounts: (params: { sector?: string; region?: string; type?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.sector) qs.set("sector", params.sector);
    if (params.region) qs.set("region", params.region);
    if (params.type) qs.set("type", params.type);
    qs.set("limit", String(params.limit ?? 100));
    return request<AccountRead[]>(`/accounts?${qs.toString()}`);
  },

  listCampaigns: (params: { status?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    qs.set("limit", String(params.limit ?? 100));
    return request<CampaignRead[]>(`/campaigns?${qs.toString()}`);
  },

  listMarketOpportunities: (params: { stage?: string; sector?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.stage) qs.set("stage", params.stage);
    if (params.sector) qs.set("sector", params.sector);
    qs.set("limit", String(params.limit ?? 100));
    return request<MarketOpportunityRead[]>(
      `/market-opportunities?${qs.toString()}`,
    );
  },

  listActiveMarketOpportunities: (limit = 50) =>
    request<MarketOpportunityRead[]>(
      `/market-opportunities/active?limit=${limit}`,
    ),

  listMarketFollowUps: (limit = 50) =>
    request<AccountCampaignRead[]>(
      `/account-campaigns/follow-ups?limit=${limit}`,
    ),

  // --- program os ---
  listPrograms: (params: { stage?: string; owner?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.stage) qs.set("stage", params.stage);
    if (params.owner) qs.set("owner", params.owner);
    qs.set("limit", String(params.limit ?? 100));
    return request<ProgramRead[]>(`/programs?${qs.toString()}`);
  },

  listActivePrograms: (limit = 50) =>
    request<ProgramRead[]>(`/programs/active?limit=${limit}`),

  listHighValuePrograms: (limit = 25) =>
    request<ProgramRead[]>(`/programs/high-value?limit=${limit}`),

  listOverduePrograms: (limit = 50) =>
    request<ProgramRead[]>(`/programs/overdue?limit=${limit}`),

  programPipelineSummary: () =>
    request<ProgramPipelineSummary>(`/programs/pipeline-summary`),

  // --- executive os ---
  executiveBriefing: () => request<DailyBriefing>(`/executive/briefing`),

  executiveActionQueue: (params: { domain?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.domain) qs.set("domain", params.domain);
    qs.set("limit", String(params.limit ?? 50));
    return request<ActionQueue>(`/executive/action-queue?${qs.toString()}`);
  },

  executiveAlerts: (severity?: string) => {
    const qs = new URLSearchParams();
    if (severity) qs.set("severity", severity);
    const q = qs.toString();
    return request<AlertBundle>(`/executive/alerts${q ? `?${q}` : ""}`);
  },

  // --- supplier os ---
  listSuppliers: (
    params: {
      type?: string;
      region?: string;
      onboarding_status?: string;
      capability?: string;
      certification?: string;
      limit?: number;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.type) qs.set("type", params.type);
    if (params.region) qs.set("region", params.region);
    if (params.onboarding_status)
      qs.set("onboarding_status", params.onboarding_status);
    if (params.capability) qs.set("capability", params.capability);
    if (params.certification) qs.set("certification", params.certification);
    qs.set("limit", String(params.limit ?? 100));
    return request<SupplierRead[]>(`/suppliers?${qs.toString()}`);
  },

  listQualifiedSuppliers: (limit = 100) =>
    request<SupplierRead[]>(`/suppliers/qualified?limit=${limit}`),

  suppliersByCapability: () =>
    request<Record<string, SupplierRead[]>>(`/suppliers/by-capability`),

  suppliersByRegion: () =>
    request<Record<string, SupplierRead[]>>(`/suppliers/by-region`),

  onboardingSummary: () =>
    request<OnboardingPipelineSummary>(`/suppliers/onboarding/summary`),

  programSuppliers: (programId: number) =>
    request<ProgramSupplierRead[]>(`/programs/${programId}/suppliers`),

  // --- investor engine writes (approval-gated outbox) ---
  engineRequestWrite: (
    externalId: string,
    payload: {
      action_type: string;
      payload: Record<string, unknown>;
      requested_by?: string;
      note?: string;
    },
  ) =>
    request<ApprovalRead>(
      `/investor-engine/writes/request/${encodeURIComponent(externalId)}`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  engineListWrites: (params: { status?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    qs.set("limit", String(params.limit ?? 100));
    return request<PendingEngineWriteRead[]>(
      `/investor-engine/writes?${qs.toString()}`,
    );
  },

  engineWritesForInvestor: (externalId: string, limit = 50) =>
    request<PendingEngineWriteRead[]>(
      `/investor-engine/writes/by-investor/${encodeURIComponent(
        externalId,
      )}?limit=${limit}`,
    ),

  engineRunWorker: (batchSize = 25) =>
    request<Record<string, unknown>>(
      `/investor-engine/writes/worker/run?batch_size=${batchSize}`,
      { method: "POST" },
    ),

  engineRetriggerWrite: (writeId: number) =>
    request<PendingEngineWriteRead>(
      `/investor-engine/writes/${writeId}/retrigger`,
      { method: "POST" },
    ),

  rejectApproval: (
    approvalId: number,
    payload: { reviewer: string; decision_note?: string },
  ) =>
    request<ApprovalRead>(`/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- intelligence os ---
  listIntel: (
    params: {
      category?: string;
      region?: string;
      tag?: string;
      min_score?: number;
      limit?: number;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.category) qs.set("category", params.category);
    if (params.region) qs.set("region", params.region);
    if (params.tag) qs.set("tag", params.tag);
    if (params.min_score !== undefined)
      qs.set("min_score", String(params.min_score));
    qs.set("limit", String(params.limit ?? 50));
    return request<IntelItemRead[]>(`/intel?${qs.toString()}`);
  },

  getIntel: (id: number) => request<IntelItemRead>(`/intel/${id}`),

  intelTopSignals: (limit = 10) =>
    request<IntelTopSignals>(`/intel/top-signals?limit=${limit}`),

  intelByCategory: (limitPerCategory = 10) =>
    request<IntelByCategory>(
      `/intel/by-category?limit_per_category=${limitPerCategory}`,
    ),

  intelByRegion: (limitPerRegion = 10) =>
    request<IntelByRegion>(
      `/intel/by-region?limit_per_region=${limitPerRegion}`,
    ),

  intelSummary: () => request<Record<string, number>>(`/intel/summary`),

  triggerIntelIngest: (actor = "ui") =>
    request<IntelIngestionReport>(
      `/intel/ingest?actor=${encodeURIComponent(actor)}`,
      { method: "POST" },
    ),

  intelAckAction: (actionId: number, actor = "ui") =>
    request<IntelActionRead>(
      `/intel/actions/${actionId}/acknowledge?actor=${encodeURIComponent(actor)}`,
      { method: "POST" },
    ),

  intelResolveAction: (actionId: number, actor = "ui") =>
    request<IntelActionRead>(
      `/intel/actions/${actionId}/resolve?actor=${encodeURIComponent(actor)}`,
      { method: "POST" },
    ),

  intelDismissAction: (actionId: number, actor = "ui") =>
    request<IntelActionRead>(
      `/intel/actions/${actionId}/dismiss?actor=${encodeURIComponent(actor)}`,
      { method: "POST" },
    ),

  // ===========================================================================
  // Sprint 0 — canonical operational core
  // ===========================================================================

  // -- Missions -------------------------------------------------------------
  listMissions: (params: {
    status?: string;
    priority?: string;
    owner_user_id?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.priority) qs.set("priority", params.priority);
    if (params.owner_user_id !== undefined)
      qs.set("owner_user_id", String(params.owner_user_id));
    const tail = qs.toString();
    return request<MissionRead[]>(`/missions${tail ? `?${tail}` : ""}`);
  },

  getMission: (id: number) => request<MissionRead>(`/missions/${id}`),

  createMission: (payload: MissionCreate) =>
    request<MissionRead>("/missions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateMission: (id: number, payload: MissionUpdate) =>
    request<MissionRead>(`/missions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteMission: (id: number) =>
    request<void>(`/missions/${id}`, { method: "DELETE" }),

  missionPressure: (id: number) =>
    request<MissionPressure>(`/missions/${id}/pressure`),

  missionDependencies: (id: number) =>
    request<MissionDependencies>(`/missions/${id}/dependencies`),

  missionTimeline: (id: number, limit = 200) =>
    request<MissionTimeline>(`/missions/${id}/timeline?limit=${limit}`),

  missionEntities: (id: number) =>
    request<MissionEntityRead[]>(`/missions/${id}/entities`),

  linkMissionEntity: (id: number, payload: MissionEntityCreate) =>
    request<MissionEntityRead>(`/missions/${id}/entities`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  unlinkMissionEntity: (missionId: number, linkId: number) =>
    request<void>(`/missions/${missionId}/entities/${linkId}`, {
      method: "DELETE",
    }),

  // -- Execution queue ------------------------------------------------------
  executionQueue: (params: {
    mission_id?: number;
    status?: string;
    item_type?: string[];
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.mission_id !== undefined)
      qs.set("mission_id", String(params.mission_id));
    if (params.status) qs.set("status", params.status);
    if (params.item_type) {
      for (const t of params.item_type) qs.append("item_type", t);
    }
    if (params.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString();
    return request<ExecutionQueue>(
      `/execution/queue${tail ? `?${tail}` : ""}`,
    );
  },

  executionBlockers: (mission_id?: number) =>
    request<ExecutionQueue>(
      `/execution/blockers${mission_id !== undefined ? `?mission_id=${mission_id}` : ""}`,
    ),

  executionPendingApprovals: (mission_id?: number) =>
    request<ExecutionQueue>(
      `/execution/approvals${mission_id !== undefined ? `?mission_id=${mission_id}` : ""}`,
    ),

  createExecutionItem: (payload: ExecutionQueueItemCreate) =>
    request<ExecutionQueueItemRead>("/execution/actions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateExecutionItem: (id: number, payload: ExecutionQueueItemUpdate) =>
    request<ExecutionQueueItemRead>(`/execution/actions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // -- Operational events ---------------------------------------------------
  events: (params: {
    since?: number;
    topic?: string;
    mission_id?: number;
    severity?: string;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.since !== undefined) qs.set("since", String(params.since));
    if (params.topic) qs.set("topic", params.topic);
    if (params.mission_id !== undefined)
      qs.set("mission_id", String(params.mission_id));
    if (params.severity) qs.set("severity", params.severity);
    if (params.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString();
    return request<OperationalEventStream>(
      `/events${tail ? `?${tail}` : ""}`,
    );
  },

  publishEvent: (payload: OperationalEventCreate) =>
    request<OperationalEventRead>("/events", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // -- Relationships --------------------------------------------------------
  listRelationships: (params: {
    source_type?: string;
    source_id?: number;
    target_type?: string;
    target_id?: number;
    relationship_type?: string;
    either_side?: boolean;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.source_type) qs.set("source_type", params.source_type);
    if (params.source_id !== undefined)
      qs.set("source_id", String(params.source_id));
    if (params.target_type) qs.set("target_type", params.target_type);
    if (params.target_id !== undefined)
      qs.set("target_id", String(params.target_id));
    if (params.relationship_type)
      qs.set("relationship_type", params.relationship_type);
    if (params.either_side) qs.set("either_side", "true");
    if (params.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString();
    return request<RelationshipRead[]>(
      `/graph/relationships${tail ? `?${tail}` : ""}`,
    );
  },

  createRelationship: (payload: RelationshipCreate) =>
    request<RelationshipRead>("/graph/relationships", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteRelationship: (id: number) =>
    request<void>(`/graph/relationships/${id}`, { method: "DELETE" }),

  // -- Auth ----------------------------------------------------------------
  authMe: () => request<CurrentUserRead>("/auth/me"),

  authLogin: (payload: LoginRequest) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  authRegister: (payload: UserCreate) =>
    request<UserRead>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // -- Mission entities (grouped) ------------------------------------------
  missionEntitiesGrouped: (id: number) =>
    request<Record<string, MissionEntityRead[]>>(
      `/missions/${id}/entities/grouped`,
    ),

  // -- Approval lifecycle on queue items -----------------------------------
  requestQueueItemApproval: (itemId: number) =>
    request<{ id: number; status: string; entity_type: string; entity_id: number; action: string }>(
      `/execution/actions/${itemId}/request-approval`,
      { method: "POST" },
    ),

  decideQueueItemApproval: (
    itemId: number,
    decision: "approved" | "rejected",
    note?: string,
  ) => {
    const qs = new URLSearchParams({ decision });
    if (note) qs.set("note", note);
    return request<{ id: number; status: string }>(
      `/execution/actions/${itemId}/decide?${qs.toString()}`,
      { method: "POST" },
    );
  },

  // -- Cognition pipeline (Sprint 5) ---------------------------------------
  cognitionCommand: (payload: CognitionCommandRequest) =>
    request<CognitionResponseRead>("/cognition/command", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  cognitionIntents: () =>
    request<IntentDescriptor[]>("/cognition/intents"),

  // -- Recommendations (Sprint 5) ------------------------------------------
  regenerateRecommendations: () =>
    request<RecommendationGenerationReport>("/recommendations/regenerate", {
      method: "POST",
    }),

  listRecommendations: (params: {
    mission_id?: number;
    status?: string;
    recommendation_type?: string;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.mission_id !== undefined)
      qs.set("mission_id", String(params.mission_id));
    if (params.status) qs.set("status", params.status);
    if (params.recommendation_type)
      qs.set("recommendation_type", params.recommendation_type);
    if (params.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString();
    return request<RecommendationRead[]>(
      `/recommendations${tail ? `?${tail}` : ""}`,
    );
  },

  missionRecommendations: (missionId: number, status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return request<RecommendationRead[]>(
      `/missions/${missionId}/recommendations${qs}`,
    );
  },

  decideRecommendation: (recId: number, payload: RecommendationDecision) =>
    request<RecommendationRead>(`/recommendations/${recId}/decide`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // -- Simulations (Sprint 5) ----------------------------------------------
  simulateSupplierFailure: (supplier_id: number) =>
    request<SimulationResultRead>("/simulations/supplier-failure", {
      method: "POST",
      body: JSON.stringify({ supplier_id }),
    }),

  simulateApprovalDelay: (approval_id: number, delay_hours = 48) =>
    request<SimulationResultRead>("/simulations/approval-delay", {
      method: "POST",
      body: JSON.stringify({ approval_id, delay_hours }),
    }),

  simulateDependencyPropagation: (
    entity_type: string,
    entity_id: number,
    depth = 2,
  ) =>
    request<SimulationResultRead>("/simulations/dependency-propagation", {
      method: "POST",
      body: JSON.stringify({ entity_type, entity_id, depth }),
    }),

  // -- Drafting (Sprint 5) -------------------------------------------------
  draftExecutiveSummary: (mission_id: number) =>
    request<SynthesisResponseRead>("/drafting/executive-summary", {
      method: "POST",
      body: JSON.stringify({ mission_id }),
    }),

  draftEscalationBrief: (mission_id: number, hours = 48) =>
    request<SynthesisResponseRead>("/drafting/escalation-brief", {
      method: "POST",
      body: JSON.stringify({ mission_id, hours }),
    }),

  // -- Intelligence signals (Sprint 4) -------------------------------------
  triggerIntelligenceIngest: (provider = "aerospace_seed", actor = "operator") =>
    request<IngestionReportRead>("/intelligence/ingest", {
      method: "POST",
      body: JSON.stringify({ provider, actor }),
    }),

  listIntelligenceSignals: (params: {
    signal_type?: string;
    severity?: string;
    region?: string;
    limit?: number;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.signal_type) qs.set("signal_type", params.signal_type);
    if (params.severity) qs.set("severity", params.severity);
    if (params.region) qs.set("region", params.region);
    if (params.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString();
    return request<SignalSummaryRead[]>(
      `/intelligence/signals${tail ? `?${tail}` : ""}`,
    );
  },

  getIntelligenceSignal: (id: number) =>
    request<SignalSummaryRead>(`/intelligence/signals/${id}`),

  signalRelevance: (id: number) =>
    request<SignalRelevanceRead[]>(`/intelligence/signals/${id}/relevance`),

  signalImpacts: (id: number) =>
    request<SignalImpactRead[]>(`/intelligence/signals/${id}/impacts`),

  missionIntelligence: (missionId: number, limit = 15) =>
    request<MissionSignalsResponse>(
      `/missions/${missionId}/intelligence?limit=${limit}`,
    ),

  executiveBrief: (hours = 24) =>
    request<SynthesisResponseRead>(
      `/executive/intelligence/brief?hours=${hours}`,
    ),

  missionIntelSynthesis: (missionId: number, hours = 24) =>
    request<SynthesisResponseRead>(
      `/missions/${missionId}/intelligence/synthesize?hours=${hours}`,
    ),

  // -- Memory + retrieval (Sprint 3) ---------------------------------------
  searchMemory: (payload: SearchQuery) =>
    request<SearchResponse>("/memory/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  memoryForMission: (missionId: number, limit = 200) =>
    request<MemoryRecordRead[]>(
      `/memory/mission/${missionId}?limit=${limit}`,
    ),

  memoryForEntity: (entityType: string, entityId: number, limit = 200) =>
    request<MemoryRecordRead[]>(
      `/memory/entity/${encodeURIComponent(entityType)}/${entityId}?limit=${limit}`,
    ),

  refreshMemoryRecord: (recordId: number) =>
    request<MemoryRecordRead>(`/memory/records/${recordId}/refresh`, {
      method: "POST",
    }),

  // -- RAG synthesis (Sprint 3) --------------------------------------------
  synthesizeMission: (missionId: number) =>
    request<SynthesisResponseRead>(`/missions/${missionId}/synthesize`, {
      method: "POST",
    }),

  synthesizePressure: (missionId: number) =>
    request<SynthesisResponseRead>(
      `/missions/${missionId}/synthesize/pressure`,
      { method: "POST" },
    ),

  synthesizeHistory: (missionId: number, days = 14) =>
    request<SynthesisResponseRead>(
      `/missions/${missionId}/synthesize/history?days=${days}`,
      { method: "POST" },
    ),

  relatedMissions: (missionId: number, limit = 6) =>
    request<RelatedMissionsResponse>(
      `/missions/${missionId}/related?limit=${limit}`,
    ),

  // -- Pressure history (Sprint 2) -----------------------------------------
  missionPressureHistory: (missionId: number, limit = 100) =>
    request<PressureHistory>(
      `/missions/${missionId}/pressure/history?limit=${limit}`,
    ),

  recomputePressure: (missionId: number) =>
    request<PressureSnapshotRead>(
      `/missions/${missionId}/pressure/recompute`,
      { method: "POST" },
    ),

  // -- Presence (Sprint 2) -------------------------------------------------
  presenceActive: (missionId?: number) => {
    const qs =
      missionId !== undefined ? `?mission_id=${missionId}` : "";
    return request<PresenceList>(`/presence/active${qs}`);
  },

  presenceForMission: (missionId: number) =>
    request<PresenceList>(`/presence/mission/${missionId}`),

  graphPropagation: (params: {
    source_type: string;
    source_id: number;
    direction?: "downstream" | "upstream" | "both";
    depth?: number;
    relationship_type?: string[];
  }) => {
    const qs = new URLSearchParams();
    qs.set("source_type", params.source_type);
    qs.set("source_id", String(params.source_id));
    if (params.direction) qs.set("direction", params.direction);
    if (params.depth) qs.set("depth", String(params.depth));
    if (params.relationship_type) {
      for (const t of params.relationship_type)
        qs.append("relationship_type", t);
    }
    return request<PropagationView>(
      `/graph/propagation?${qs.toString()}`,
    );
  },
};

export { ApiError };
