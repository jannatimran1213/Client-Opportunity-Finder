'use client';
// Module 1 - Multi-Tenant Workspace, Role-Based Access Control and Workspace Management (team panel).
import { useEffect, useState } from 'react';
import { api, fmtDate, setWorkspaceId } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Input, PageHeader, Select, Table, Tabs, Textarea, useCopy } from '../components/ui';

const ROLE_COLORS = { owner: 'purple', admin: 'blue', member: 'green', viewer: 'gray' };

export default function WorkspacePage() {
  const toast = useToast();
  const copy = useCopy();
  const [tab, setTab] = useState('team');
  const [ws, setWs] = useState(null);
  const [team, setTeam] = useState({ members: [], pending_invites: [], my_role: 'viewer' });
  const [roles, setRoles] = useState({ roles: [], permissions: [], matrix: {} });
  const [invite, setInvite] = useState({ email: '', role: 'member' });
  const [newWs, setNewWs] = useState('');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [w, m, r] = await Promise.all([api('/workspaces/current'), api('/workspaces/members'), api('/workspaces/roles')]);
      setWs(w); setTeam(m); setRoles(r);
    } catch (e) { toast(e.message, 'error'); }
  }
  useEffect(() => { load(); }, []);

  const canManage = ['owner', 'admin'].includes(team.my_role);

  async function sendInvite(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api('/workspaces/members/invite', { method: 'POST', body: invite });
      toast(r.email_sent ? 'Invite emailed' : 'Invite created: copy the link below and send it', 'success');
      setInvite({ email: '', role: 'member' });
      load();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  }

  async function changeRole(m, role) {
    try { await api(`/workspaces/members/${m.id}/role`, { method: 'PUT', body: { role } }); toast('Role updated', 'success'); load(); }
    catch (e) { toast(e.message, 'error'); }
  }
  async function removeMember(m) {
    if (!confirm(`Remove ${m.full_name || m.email} from this workspace?`)) return;
    try { await api(`/workspaces/members/${m.id}`, { method: 'DELETE' }); toast('Member removed', 'success'); load(); }
    catch (e) { toast(e.message, 'error'); }
  }
  async function revoke(i) {
    try { await api(`/workspaces/invites/${i.id}`, { method: 'DELETE' }); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function saveSettings(e) {
    e.preventDefault();
    try {
      const r = await api('/workspaces/current', { method: 'PUT', body: {
        name: ws.name, company_name: ws.company_name, company_website: ws.company_website, services: ws.services,
        settings: { ...(ws.settings || {}), no_reply_days: Number(ws.settings?.no_reply_days || 3) } } });
      setWs({ ...ws, ...r }); toast('Workspace saved', 'success');
    } catch (e) { toast(e.message, 'error'); }
  }
  async function createWs(e) {
    e.preventDefault();
    try {
      const r = await api('/workspaces', { method: 'POST', body: { name: newWs } });
      setWorkspaceId(r.id); toast('Workspace created and selected', 'success'); window.location.reload();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function acceptInvite(e) {
    e.preventDefault();
    try {
      const t = token.includes('invite=') ? new URL(token).searchParams.get('invite') : token.trim();
      const r = await api('/workspaces/invites/accept', { method: 'POST', body: { token: t } });
      if (r.workspace_id) setWorkspaceId(r.workspace_id);
      toast('Joined workspace', 'success'); window.location.reload();
    } catch (e) { toast(e.message, 'error'); }
  }

  const memberCols = [
    { label: 'Member', render: (m) => <div><p className="font-bold text-slate-900 dark:text-white">{m.full_name || '-'}</p><p className="text-xs">{m.email}</p></div> },
    { label: 'Role', render: (m) => (canManage && m.role !== 'owner'
      ? <select value={m.role} onChange={(e) => changeRole(m, e.target.value)} className="rounded-lg border border-slate-200 bg-transparent px-2 py-1 text-xs font-bold dark:border-white/10">
          {['admin', 'member', 'viewer'].map((r) => <option key={r} value={r} className="text-black">{r}</option>)}
        </select>
      : <Badge color={ROLE_COLORS[m.role]}>{m.role}</Badge>) },
    { label: 'Leads added', key: 'leads_added' },
    { label: 'Meetings booked', key: 'meetings_booked' },
    { label: 'Last activity', render: (m) => fmtDate(m.last_activity) },
    { label: 'Joined', render: (m) => fmtDate(m.joined_at, false) },
    { label: '', render: (m) => (canManage && m.role !== 'owner' ? <Button variant="ghost" onClick={() => removeMember(m)}>Remove</Button> : null) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader module="[1] Sign Up & SaaS Access · Multi-Tenant Workspace + Role-Based Access Control" title={ws?.name || 'Workspace'}
        subtitle={`Your role: ${team.my_role}. Every lead, audit, page and message is private to this workspace (multi-tenant isolation).`} />
      <Tabs active={tab} onChange={setTab} tabs={[
        { id: 'team', label: 'Multi-Tenant Workspace' }, { id: 'roles', label: 'Role-Based Access Control' },
        { id: 'settings', label: 'Workspace settings' }, { id: 'workspaces', label: 'Workspaces' }]} />

      {tab === 'team' && (
        <div className="space-y-6">
          {canManage && (
            <Card title="Invite a team member">
              <form onSubmit={sendInvite} className="grid gap-3 md:grid-cols-[1fr_180px_auto] md:items-end">
                <Input label="Email" type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} />
                <Select label="Role" value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })} options={['admin', 'member', 'viewer']} />
                <Button loading={busy}>Send invite</Button>
              </form>
            </Card>
          )}
          <Card title={`Members (${team.members.length})`}><Table columns={memberCols} rows={team.members} empty="No members" /></Card>
          {team.pending_invites.length > 0 && (
            <Card title="Pending invites">
              <div className="space-y-2">
                {team.pending_invites.map((i) => (
                  <div key={i.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05]">
                    <span><b>{i.email}</b> · <Badge color={ROLE_COLORS[i.role]}>{i.role}</Badge></span>
                    <span className="flex gap-2">
                      <Button variant="secondary" onClick={async () => toast((await copy(i.invite_link)) ? 'Invite link copied' : i.invite_link, 'info')}>Copy link</Button>
                      {canManage && <Button variant="ghost" onClick={() => revoke(i)}>Revoke</Button>}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {tab === 'roles' && (
        <Card title="Role-Based Access Control matrix">
          <div className="mb-4 grid gap-3 md:grid-cols-4">
            {roles.roles.map((r) => (
              <div key={r.role} className="rounded-lg border border-slate-100 p-3 dark:border-white/[0.05]">
                <Badge color={ROLE_COLORS[r.role]}>{r.role}</Badge>
                <p className="mt-2 text-xs text-slate-500 dark:text-[#8E8BA3]">{r.description}</p>
              </div>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="py-2">Permission</th>{roles.roles.map((r) => <th key={r.role} className="py-2 text-center">{r.role}</th>)}</tr></thead>
              <tbody>
                {roles.permissions.map((p) => (
                  <tr key={p} className="border-t border-slate-100 dark:border-white/[0.04]">
                    <td className="py-2 font-mono text-xs text-slate-700 dark:text-[#C8C4E8]">{p}</td>
                    {roles.roles.map((r) => <td key={r.role} className="py-2 text-center">{roles.matrix?.[r.role]?.[p] ? '✅' : '—'}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-400">Enforced on the server by SecurityManager (app/core/security.py) on every API call.</p>
        </Card>
      )}

      {tab === 'settings' && ws && (
        <Card title="Workspace settings">
          <form onSubmit={saveSettings} className="grid gap-4 md:grid-cols-2">
            <Input label="Workspace name" value={ws.name || ''} onChange={(e) => setWs({ ...ws, name: e.target.value })} disabled={!canManage} />
            <Input label="Agency / company name (used to sign emails)" value={ws.company_name || ''} onChange={(e) => setWs({ ...ws, company_name: e.target.value })} disabled={!canManage} />
            <Input label="Agency website" value={ws.company_website || ''} onChange={(e) => setWs({ ...ws, company_website: e.target.value })} disabled={!canManage} />
            <Input label="Smart reminder: alert when no reply after (days)" type="number" min="1" value={ws.settings?.no_reply_days || 3}
              onChange={(e) => setWs({ ...ws, settings: { ...(ws.settings || {}), no_reply_days: e.target.value } })} disabled={!canManage} />
            <Textarea className="md:col-span-2" label="Services you sell (the AI copywriter pitches these)" value={ws.services || ''}
              onChange={(e) => setWs({ ...ws, services: e.target.value })} placeholder="Web design, SEO, Google Ads..." disabled={!canManage} />
            {canManage && <div><Button>Save settings</Button></div>}
          </form>
        </Card>
      )}

      {tab === 'workspaces' && (
        <div className="grid gap-6 md:grid-cols-2">
          <Card title="Create another workspace">
            <form onSubmit={createWs} className="space-y-3">
              <Input label="Name" required value={newWs} onChange={(e) => setNewWs(e.target.value)} placeholder="e.g. Client: Dubai Dental" />
              <Button>Create & switch</Button>
            </form>
          </Card>
          <Card title="Join a workspace with an invite">
            <form onSubmit={acceptInvite} className="space-y-3">
              <Input label="Invite link or token" required value={token} onChange={(e) => setToken(e.target.value)} />
              <Button variant="secondary">Join</Button>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
