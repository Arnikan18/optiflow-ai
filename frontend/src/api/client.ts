import type {
  CreateRunResponse,
  RunSummary,
  ApproveRunPayload,
  ClarifyRunPayload,
} from '../types/api';

const BASE = '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  // ── Runs ──────────────────────────────────────────────────────
  createRun(goal_text: string): Promise<CreateRunResponse> {
    return request('/runs', {
      method: 'POST',
      body: JSON.stringify({ goal_text }),
    });
  },

  getRunStatus(run_id: string): Promise<RunSummary> {
    return request(`/runs/${run_id}`);
  },

  approveRun(run_id: string, payload: ApproveRunPayload): Promise<{ status: string; message: string }> {
    return request(`/runs/${run_id}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  clarifyRun(run_id: string, payload: ClarifyRunPayload): Promise<{ status: string; message: string }> {
    return request(`/runs/${run_id}/clarify`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // ── System ────────────────────────────────────────────────────
  getSystemHealth(): Promise<Record<string, unknown>> {
    return request('/system/health');
  },

  getDemoPortfolio(): Promise<Record<string, unknown>> {
    return request('/demo/portfolio');
  },

  resetSystem(): Promise<{ status: string }> {
    return request('/control-room/reset', { method: 'POST' });
  },
};
