'use client';
// Shared API client for the 32-feature modules.
// Adds the JWT and the active workspace (multi-tenant) header to every request.

export const API_BASE = '/api/v1';
export const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ai-client-hunting-backend.onrender.com';

export function getToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('access_token') || localStorage.getItem('token') || '';
}

export function getWorkspaceId() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('workspace_id') || '';
}

export function setWorkspaceId(id) {
  localStorage.setItem('workspace_id', id);
  window.dispatchEvent(new Event('workspace-changed'));
}

function headers(extra = {}, json = true) {
  const h = { ...extra };
  if (json) h['Content-Type'] = 'application/json';
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  const ws = getWorkspaceId();
  if (ws) h['X-Workspace-Id'] = ws;
  return h;
}

export async function api(path, { method = 'GET', body, raw = false, params } = {}) {
  let url = `${API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
    if ([...qs].length) url += `?${qs}`;
  }
  const res = await fetch(url, { method, headers: headers(), body: body !== undefined ? JSON.stringify(body) : undefined });
  if (raw) {
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    return res;
  }
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : `Request failed (${res.status})`;
    if (res.status === 403 && msg.includes('not a member')) localStorage.removeItem('workspace_id');
    throw new Error(msg);
  }
  return data;
}

export async function apiText(path, body) {
  const res = await fetch(`${API_BASE}${path}`, { method: body ? 'POST' : 'GET', headers: headers(), body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.text();
}

export async function download(path, filename) {
  const res = await fetch(`${API_BASE}${path}`, { headers: headers({}, false) });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function fmtDate(iso, withTime = true) {
  if (!iso) return '-';
  const d = new Date(iso);
  return withTime ? d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

// Background jobs (Celery + Redis on the server, or in-process fallback). Queues the job and polls until it ends.
export async function runJob(kind, payload, { onStatus, intervalMs = 1500, timeoutMs = 15 * 60 * 1000 } = {}) {
  const job = await api('/jobs', { method: 'POST', body: { kind, payload } });
  onStatus?.(job);
  const started = Date.now();
  for (;;) {
    await new Promise((r) => setTimeout(r, intervalMs));
    const j = await api(`/jobs/${job.id}`);
    onStatus?.(j);
    if (j.status === 'completed') return j.result;
    if (j.status === 'failed') throw new Error(j.error || 'Job failed');
    if (Date.now() - started > timeoutMs) throw new Error('Job is still running - check Background Jobs later');
  }
}
