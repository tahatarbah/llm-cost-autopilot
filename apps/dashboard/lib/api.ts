const GATEWAY =
  process.env.NEXT_PUBLIC_GATEWAY_URL ||
  process.env.GATEWAY_URL ||
  "http://localhost:8080";

export function getAdminToken(): string {
  if (typeof window === "undefined") {
    return process.env.GATEWAY_SECRET || "dev-secret-change-me";
  }
  return localStorage.getItem("lca_admin_token") || "dev-secret-change-me";
}

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("lca_org_id");
}

export async function adminFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Admin-Token", getAdminToken());
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${GATEWAY}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export function getGatewayUrl(): string {
  if (typeof window !== "undefined") {
    return (
      localStorage.getItem("lca_gateway_url") ||
      process.env.NEXT_PUBLIC_GATEWAY_URL ||
      "http://localhost:8080"
    );
  }
  return GATEWAY;
}

export function getPlaygroundKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("lca_api_key") || "";
}

export function setPlaygroundKey(key: string) {
  localStorage.setItem("lca_api_key", key);
}

export type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

export type AutopilotMeta = {
  cost_usd: string | null;
  estimate_usd: string | null;
  model_used: string | null;
  cache: string | null;
  request_id: string | null;
  provider: string | null;
  budget_alert: string | null;
};

export async function playgroundChat(args: {
  apiKey: string;
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
}): Promise<{ body: Record<string, unknown>; meta: AutopilotMeta; status: number }> {
  const base = getGatewayUrl();
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${args.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: args.model,
      messages: args.messages,
      temperature: args.temperature,
      max_tokens: args.max_tokens,
    }),
  });
  const meta: AutopilotMeta = {
    cost_usd: res.headers.get("x-llm-cost-usd"),
    estimate_usd: res.headers.get("x-llm-estimate-usd"),
    model_used: res.headers.get("x-llm-model-used"),
    cache: res.headers.get("x-llm-cache"),
    request_id: res.headers.get("x-llm-request-id"),
    provider: res.headers.get("x-llm-provider"),
    budget_alert: res.headers.get("x-llm-budget-alert"),
  };
  const body = await res.json();
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail || body);
    throw new Error(`${res.status}: ${detail}`);
  }
  return { body, meta, status: res.status };
}

export async function playgroundModels(apiKey: string): Promise<
  Array<{ id: string; resolves_to: string; provider: string }>
> {
  const base = getGatewayUrl();
  const res = await fetch(`${base}/v1/models`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const data = await res.json();
  return (data.data || []).map((m: { id: string; resolves_to: string; provider: string }) => ({
    id: m.id,
    resolves_to: m.resolves_to,
    provider: m.provider,
  }));
}

export async function playgroundEstimate(
  apiKey: string,
  model: string,
  messages: ChatMessage[],
  expected_output_tokens = 256
): Promise<{ estimated_cost_usd: number; resolved_model: string; input_tokens: number }> {
  const base = getGatewayUrl();
  const res = await fetch(`${base}/v1/estimate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model, messages, expected_output_tokens }),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export type Org = { id: string; name: string; slug: string };
export type Project = { id: string; org_id: string; name: string; slug: string };
export type SpendSummary = {
  today_usd: number;
  month_usd: number;
  request_count: number;
  cache_hit_rate: number;
  by_model: Array<{
    model: string;
    requests: number;
    cost_usd: number;
    input_tokens: number;
    output_tokens: number;
  }>;
  by_project: Array<{
    project: string;
    project_id: string;
    requests: number;
    cost_usd: number;
  }>;
};
export type UsageEvent = {
  id: string;
  project_id: string;
  model: string;
  provider: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cache_hit: boolean;
  latency_ms: number;
  created_at: string;
  status: string;
};
export type Budget = {
  id: string;
  org_id: string;
  project_id: string | null;
  scope: string;
  period: string;
  limit_usd: number;
  action: string;
  alert_threshold: number;
  spent_usd: number;
};
export type ApiKey = {
  id: string;
  project_id: string;
  name: string;
  prefix: string;
  created_at: string;
  key?: string | null;
};
