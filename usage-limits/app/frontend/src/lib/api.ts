import axios from "axios";

const api = axios.create({ baseURL: "/" });

export interface OverviewMetrics {
  cost_today: number;
  requests_today: number;
  active_users: number;
}

export interface TopUser {
  requester: string;
  total_tokens: number;
  request_count: number;
}

export interface UserUsageDay {
  usage_date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface UserUsageHistory {
  user_email: string;
  days: UserUsageDay[];
  total_tokens_30d: number;
  daily_average: number;
}

export interface UserSnapshot {
  user_id: string;
  dollar_cost_1d: number | null;
  dollar_cost_7d: number | null;
  dollar_cost_30d: number | null;
  total_tokens_1d: number | null;
  total_tokens_7d: number | null;
  total_tokens_30d: number | null;
  request_count_1d: number | null;
  request_count_7d: number | null;
  request_count_30d: number | null;
}

export interface BudgetConfig {
  id: number;
  entity_type: string;
  entity_id: string;
  daily_dollar_limit: number | null;
  weekly_dollar_limit: number | null;
  monthly_dollar_limit: number | null;
  is_custom: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface DefaultBudget {
  id: number;
  daily_dollar_limit: number | null;
  weekly_dollar_limit: number | null;
  monthly_dollar_limit: number | null;
  updated_at: string | null;
}

export interface Warning {
  id: number;
  user_id: string;
  reason: string;
  dollar_usage: number | null;
  dollar_limit: number | null;
  enforced_at: string | null;
  expires_at: string | null;
  is_active: boolean;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  user_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

// Auth
export interface MeResponse {
  email: string;
  display_name: string;
  is_admin: boolean;
}
export const getMe = () => api.get<MeResponse>("/api/me").then((r) => r.data);

// My Usage
export interface MyBudgetStatus {
  daily_dollar_limit: number | null;
  weekly_dollar_limit: number | null;
  monthly_dollar_limit: number | null;
  dollar_cost_1d: number | null;
  dollar_cost_7d: number | null;
  dollar_cost_30d: number | null;
}
export const getMySnapshot = () => api.get<UserSnapshot | null>("/api/my-usage/snapshot").then((r) => r.data);
export const getMyHistory = (days = 30) => api.get<UserUsageHistory>(`/api/my-usage/history?days=${days}`).then((r) => r.data);
export const getMyBudget = () => api.get<MyBudgetStatus | null>("/api/my-usage/budget").then((r) => r.data);

// Overview
export const getOverviewMetrics = () => api.get<OverviewMetrics>("/api/overview/metrics").then((r) => r.data);
export const getTopUsers = () => api.get<TopUser[]>("/api/overview/top-users").then((r) => r.data);

// Users
export const listUsers = () => api.get<string[]>("/api/users/").then((r) => r.data);
export const getUserUsage = (email: string, days = 30) =>
  api.get<UserUsageHistory>(`/api/users/${encodeURIComponent(email)}/usage?days=${days}`).then((r) => r.data);
export const getUserSnapshot = (email: string) =>
  api.get<UserSnapshot | null>(`/api/users/${encodeURIComponent(email)}/snapshot`).then((r) => r.data);
export const getUserBudget = (email: string) =>
  api.get<BudgetConfig | null>(`/api/users/${encodeURIComponent(email)}/budget`).then((r) => r.data);

// Budgets
export const listBudgets = () => api.get<BudgetConfig[]>("/api/budgets/").then((r) => r.data);
export const saveBudget = (data: { entity_id: string; daily_dollar_limit?: number | null; weekly_dollar_limit?: number | null; monthly_dollar_limit?: number | null }) =>
  api.post<BudgetConfig>("/api/budgets/", data).then((r) => r.data);
export const deleteBudget = (id: number) => api.delete(`/api/budgets/${id}`).then((r) => r.data);
export const getDefaultBudget = () => api.get<DefaultBudget | null>("/api/budgets/default").then((r) => r.data);
export const saveDefaultBudget = (data: { daily_dollar_limit?: number | null; weekly_dollar_limit?: number | null; monthly_dollar_limit?: number | null }) =>
  api.post<DefaultBudget>("/api/budgets/default", data).then((r) => r.data);

// Warnings
export const listActiveWarnings = () => api.get<Warning[]>("/api/warnings/").then((r) => r.data);
export const resolveWarning = (warningId: number) => api.post("/api/warnings/resolve", { warning_id: warningId }).then((r) => r.data);

// Audit
export const listAuditLog = (limit = 100) => api.get<AuditLogEntry[]>(`/api/audit/?limit=${limit}`).then((r) => r.data);

