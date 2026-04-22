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
};

export { ApiError };
