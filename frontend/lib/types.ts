// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id:            string;
  email:         string;
  full_name:     string | null;
  role:          "admin" | "member" | "viewer";
  is_active:     boolean;
  created_at:    string | null;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type:   "bearer";
  expires_in:   number;
  user:         User;
}

// ── Campaigns ─────────────────────────────────────────────────────────────────

export interface Campaign {
  id:         string;
  name:       string;
  brief:      string;
  objective:  string;
  kpis:       Record<string, unknown>;
  start_date: string;
  end_date:   string;
  status:     "draft" | "active" | "paused" | "completed" | "archived";
  created_at: string | null;
  updated_at: string | null;
}

export interface CampaignCreate {
  name:       string;
  brief:      string;
  objective:  string;
  kpis:       Record<string, unknown>;
  start_date: string;
  end_date:   string;
  platforms:  string[];
}

export interface CampaignUpdate {
  name?:       string;
  status?:     string;
  start_date?: string;
  end_date?:   string;
  kpis?:       Record<string, unknown>;
}

// ── Posts ─────────────────────────────────────────────────────────────────────

export interface Post {
  id:              string;
  campaign_id:     string | null;
  platform:        string;
  pillar_id:       string | null;
  scheduled_at:    string | null;
  status:          string;
  copy:            string | null;
  visual_url:      string | null;
  approval_status: string;
  metadata_json:   Record<string, unknown>;
  created_at:      string | null;
  updated_at:      string | null;
}

export interface PostSlot {
  id:              string;
  campaign_id:     string | null;
  platform:        string;
  pillar_id:       string | null;
  scheduled_at:    string | null;
  status:          string;
  copy:            string | null;
  visual_url:      string | null;
  approval_status: string;
  metadata_json:   Record<string, unknown>;
}

export interface PostVersion {
  id:             string;
  post_id:        string;
  version_number: number;
  copy:           string | null;
  visual_url:     string | null;
  scheduled_at:   string | null;
  edited_by:      string | null;
  created_at:     string | null;
}

// ── Approvals ─────────────────────────────────────────────────────────────────

export interface ApprovalQueueItem {
  post_id:       string;
  campaign_id:   string;
  campaign_name: string;
  platform:      string;
  copy:          string | null;
  visual_url:    string | null;
  scheduled_at:  string | null;
  created_at:    string | null;
}

export interface ApprovalQueueCount {
  count: number;
}

export interface ApprovalHistoryItem {
  id:        string;
  post_id:   string;
  reviewer:  string;
  decision:  string;
  feedback:  string | null;
  timestamp: string | null;
}

// ── Calendar ──────────────────────────────────────────────────────────────────

export interface CampaignCalendar {
  campaign: Campaign;
  posts:    PostSlot[];
  total:    number;
}

// ── Compliance ────────────────────────────────────────────────────────────────

export interface ComplianceFlag {
  word:     string;
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  position: number;
  length:   number;
}

export interface ComplianceCheckResult {
  passed:      boolean;
  flags:       ComplianceFlag[];
  suggestions: string[];
}

export interface SensitiveWord {
  id:         string;
  word:       string;
  language:   string;
  severity:   string;
  category:   string | null;
  created_at: string | null;
}

// ── Ad Creative ───────────────────────────────────────────────────────────────

export interface AdVariant {
  headline:     string;
  primary_text: string;
  description:  string | null;
  cta_button:   string;
  visual_brief: string;
  rationale:    string;
}

export interface AdCreativeOutput {
  variants:                  AdVariant[];
  recommended_test_priority: number[];
  targeting_notes:           string;
}

export interface AdCreativeRun {
  id:          string;
  user_id:     string | null;
  campaign_id: string | null;
  platform:    string;
  input_json:  Record<string, unknown>;
  output_json: Record<string, unknown>;
  created_at:  string | null;
}

// ── Assets ────────────────────────────────────────────────────────────────────

export interface Asset {
  id:                string;
  type:              "image" | "video" | "document";
  url:               string;
  name:              string | null;
  tags:              string[];
  performance_score: number | null;
  created_at:        string | null;
}

// ── Agent Logs ────────────────────────────────────────────────────────────────

export interface AgentLog {
  id:          string;
  agent_name:  string;
  task:        string;
  input_json:  Record<string, unknown>;
  output_json: Record<string, unknown> | null;
  status:      "running" | "success" | "failed";
  duration_ms: number | null;
  timestamp:   string | null;
}

// ── Brand ─────────────────────────────────────────────────────────────────────

export interface BrandContext {
  content: string;
  source:  string;
}

export interface SkillList {
  external: string[];
  custom:   string[];
}

// ── Meta Ads ──────────────────────────────────────────────────────────────────

export interface AdCampaign {
  id:                string;
  campaign_id:       string | null;
  meta_campaign_id:  string;
  meta_adset_id:     string | null;
  meta_ad_id:        string | null;
  status:            "PAUSED" | "ACTIVE" | "ARCHIVED" | "DELETED" | string;
  daily_budget:      number | null;
  daily_budget_aud:  number | null;
  objective:         string | null;
  targeting_summary: string | null;
  synced_at:         string | null;
  created_at:        string | null;
  updated_at:        string | null;
}

export interface CreateAdCampaignRequest {
  name:                string;
  daily_budget_aud:    number;
  targeting_location:  string;
  targeting_interests: string;
  campaign_id?:        string;
}

export interface AdInsights {
  meta_campaign_id: string;
  reach:            number;
  impressions:      number;
  clicks:           number;
  ctr:              number;
  spend_aud:        number;
  leads:            number;
  cpl_aud:          number;
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginationParams {
  page?:      number;
  page_size?: number;
}

// ── API Error ─────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
}
