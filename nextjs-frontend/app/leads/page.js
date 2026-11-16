'use client';
// Module 3 - Lead Management: Save Promising Businesses, Edit and Organize Lists, Validation Filter,
// Lead Duplication Check (+ merge). Also links each lead to its audit, AI copy and discussion timeline.
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api, download, fmtDate, runJob } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, Modal, PageHeader, Select, statusColor, Table, Tabs, Textarea, Toggle } from '../components/ui';

const STATUSES = ['new', 'contacted', 'replied', 'meeting', 'won', 'lost'];
const blank = { business_name: '', website: '', email: '', phone: '', city: '', country: '', category: '', address: '', notes: '' };

export default function LeadsPage() {
  const toast = useToast();
  const [tab, setTab] = useState('leads');
  const [data, setData] = useState({ leads: [], total: 0 });
  const [stats, setStats] = useState(null);
  const [lists, setLists] = useState([]);
  const [filters, setFilters] = useState({ q: '', status: '', list_id: '', email_status: '', has_email: '' });
  const [sel, setSel] = useState({});
  const [edit, setEdit] = useState(null);
  const [add, setAdd] = useState(null);
  const [newList, setNewList] = useState({ name: '', description: '', color: '#6D5DF6' });
  const [dups, setDups] = useState(null);
  const [val, setVal] = useState({ check_website: true, check_mx: true });
  const [valRes, setValRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [timeline, setTimeline] = useState(null);

  async function load() {
    try {
      const [d, s, l] = await Promise.all([api('/leads', { params: { ...filters, per_page: 200 } }), api('/leads/stats'), api('/leads/lists')]);
      setData(d); setStats(s); setLists(l.lists || []); setSel({});
    } catch (e) { toast(e.message, 'error'); }
  }
  useEffect(() => { load(); }, [filters.status, filters.list_id, filters.email_status, filters.has_email]);

  const ids = useMemo(() => Object.keys(sel).filter((k) => sel[k]), [sel]);

  async function bulk(action, value) {
    if (!ids.length) return toast('Select leads first', 'warning');
    if (action === 'delete' && !confirm(`Delete ${ids.length} leads?`)) return;
    try { await api('/leads/bulk', { method: 'POST', body: { ids, action, value } }); toast('Done', 'success'); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function saveEdit(e) {
    e.preventDefault();
    try {
      const { id, business_name, website, email, phone, address, city, country, category, notes, status, priority, linkedin_url, whatsapp_number } = edit;
      await api(`/leads/${id}`, { method: 'PUT', body: { business_name, website, email, phone, address, city, country, category, notes, status, priority,
        linkedin_url, whatsapp_number, tags: typeof edit.tags === 'string' ? edit.tags.split(',').map((t) => t.trim()).filter(Boolean) : edit.tags } });
      toast('Lead updated', 'success'); setEdit(null); load();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function saveNew(e) {
    e.preventDefault();
    try {
      const r = await api('/leads/save', { method: 'POST', body: { businesses: [add], list_id: filters.list_id || undefined, skip_duplicates: true } });
      toast(r.skipped_duplicates ? 'Already in your leads (duplicate skipped)' : 'Lead saved', r.skipped_duplicates ? 'warning' : 'success'); setAdd(null); load();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function createList(e) {
    e.preventDefault();
    try { await api('/leads/lists', { method: 'POST', body: newList }); setNewList({ name: '', description: '', color: '#6D5DF6' }); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function renameList(l) {
    const name = prompt('List name', l.name); if (!name) return;
    try { await api(`/leads/lists/${l.id}`, { method: 'PUT', body: { name, description: l.description, color: l.color } }); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function deleteList(l) {
    if (!confirm(`Delete list "${l.name}"? Leads stay saved.`)) return;
    try { await api(`/leads/lists/${l.id}`, { method: 'DELETE' }); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function validate() {
    setBusy(true); setValRes(null);
    try {
      const r = await runJob('validate_leads', { ids: ids.length ? ids : undefined, all: !ids.length, ...val });
      setValRes(r); toast(`Checked ${r.summary.checked} leads`, 'success'); load();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(false); }
  }
  async function loadDups() {
    try { setDups(await api('/leads/duplicates')); } catch (e) { toast(e.message, 'error'); }
  }
  async function merge(g) {
    const keep = g.keep_suggestion;
    try {
      await api('/leads/duplicates/merge', { method: 'POST', body: { keep_id: keep, merge_ids: g.leads.map((l) => l.id).filter((i) => i !== keep) } });
      toast('Merged', 'success'); loadDups(); load();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function openTimeline(l) {
    try { setTimeline(await api(`/meetings/timeline/${l.id}`)); } catch (e) { toast(e.message, 'error'); }
  }
  useEffect(() => { if (tab === 'duplicates') loadDups(); }, [tab]);

  const leadCols = [
    { label: <input type="checkbox" className="accent-[#6D5DF6]" checked={data.leads.length > 0 && ids.length === data.leads.length}
        onChange={(e) => setSel(Object.fromEntries(data.leads.map((l) => [l.id, e.target.checked])))} />, key: 'sel',
      render: (l) => <input type="checkbox" className="accent-[#6D5DF6]" checked={!!sel[l.id]} onChange={(e) => setSel({ ...sel, [l.id]: e.target.checked })} /> },
    { label: 'Business', key: 'name', render: (l) => <div><button onClick={() => setEdit({ ...l, tags: (l.tags || []).join(', ') })} className="text-left font-bold text-slate-900 hover:text-[#6D5DF6] dark:text-white">{l.business_name}</button>
      <p className="text-xs">{[l.category, l.city].filter(Boolean).join(' · ')}</p>
      {l.tags?.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{l.tags.map((t) => <Badge key={t} color="purple">{t}</Badge>)}</div>}</div> },
    { label: 'Contact', key: 'contact', render: (l) => <div className="text-xs">
      <p>{l.email || '-'} {l.email_status && <Badge color={statusColor(l.email_status)}>{l.email_status}</Badge>}</p>
      <p>{l.phone_e164 || l.phone || '-'} {l.phone_status && l.phone_status !== 'missing' && <Badge color={statusColor(l.phone_status)}>{l.phone_status}</Badge>}</p>
      <p>{l.website ? <a href={l.website} target="_blank" rel="noreferrer" className="text-[#6D5DF6]">{l.website.replace(/^https?:\/\//, '').slice(0, 28)}</a> : '-'} {l.website_status && l.website_status !== 'skipped' && <Badge color={statusColor(l.website_status)}>{l.website_status}</Badge>}</p></div> },
    { label: 'Score', key: 'score', render: (l) => <div className="text-xs"><p>Audit: <b>{l.overall_score ?? '-'}</b></p><p>Valid: <b>{l.validation_score ?? '-'}</b></p></div> },
    { label: 'Stage', key: 'status', render: (l) => <Badge color={statusColor(l.status)}>{l.status}</Badge> },
    { label: 'Priority', key: 'priority', render: (l) => <Badge color={l.priority === 'high' ? 'red' : l.priority === 'low' ? 'gray' : 'amber'}>{l.priority}</Badge> },
    { label: '', key: 'actions', render: (l) => <div className="flex flex-col gap-1 text-xs font-bold">
      <Link href={`/advanced-audits?business_id=${l.id}`} className="text-[#6D5DF6]">Audit</Link>
      <Link href={`/copywriter?business_id=${l.id}`} className="text-[#6D5DF6]">Write</Link>
      <button onClick={() => openTimeline(l)} className="text-left text-[#6D5DF6]">Timeline</button></div> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader module="[3] Lead Management" title="Lead Management"
        subtitle="Saved businesses, organised into lists, validated and de-duplicated before any outreach."
        actions={<><Button variant="secondary" onClick={() => download(`/leads/export.csv${filters.list_id ? `?list_id=${filters.list_id}` : ''}`, 'leads.csv')}>Export CSV</Button>
          <Button onClick={() => setAdd({ ...blank })}>Add lead</Button></>} />

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-7">
          <Stat label="Total" value={stats.total} />
          {STATUSES.map((s) => <Stat key={s} label={s} value={stats.by_status?.[s] ?? 0} onClick={() => setFilters({ ...filters, status: filters.status === s ? '' : s })} active={filters.status === s} />)}
        </div>
      )}

      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'leads', label: `Save Promising Businesses (${data.total})` }, { id: 'lists', label: `Edit and Organize Lists (${lists.length})` },
        { id: 'validate', label: 'Validation Filter' }, { id: 'duplicates', label: 'Lead Duplication Check' }]} />

      {tab === 'leads' && (
        <Card>
          <div className="mb-4 grid gap-3 md:grid-cols-5">
            <form onSubmit={(e) => { e.preventDefault(); load(); }} className="md:col-span-2"><Input placeholder="Search name, email, city... (Enter)" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} /></form>
            <Select value={filters.list_id} onChange={(e) => setFilters({ ...filters, list_id: e.target.value })} options={[{ value: '', label: 'All lists' }, ...lists.map((l) => ({ value: l.id, label: `${l.name} (${l.count})` }))]} />
            <Select value={filters.email_status} onChange={(e) => setFilters({ ...filters, email_status: e.target.value })} options={[{ value: '', label: 'Any email status' }, 'valid', 'risky', 'invalid', 'unknown']} />
            <Select value={filters.has_email} onChange={(e) => setFilters({ ...filters, has_email: e.target.value })} options={[{ value: '', label: 'With or without email' }, { value: 'true', label: 'Has email' }, { value: 'false', label: 'No email' }]} />
          </div>
          {ids.length > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg bg-violet-50 p-3 text-sm dark:bg-violet-500/10">
              <b>{ids.length} selected</b>
              <select onChange={(e) => { if (e.target.value) bulk('set_status', e.target.value); e.target.value = ''; }} className="rounded-lg border bg-transparent px-2 py-1 text-xs">
                <option value="">Set stage...</option>{STATUSES.map((s) => <option key={s} value={s} className="text-black">{s}</option>)}</select>
              <select onChange={(e) => { if (e.target.value) bulk('set_priority', e.target.value); e.target.value = ''; }} className="rounded-lg border bg-transparent px-2 py-1 text-xs">
                <option value="">Set priority...</option>{['high', 'medium', 'low'].map((s) => <option key={s} value={s} className="text-black">{s}</option>)}</select>
              <select onChange={(e) => { if (e.target.value) bulk('add_to_list', e.target.value); e.target.value = ''; }} className="rounded-lg border bg-transparent px-2 py-1 text-xs">
                <option value="">Add to list...</option>{lists.map((l) => <option key={l.id} value={l.id} className="text-black">{l.name}</option>)}</select>
              {filters.list_id && <Button variant="secondary" onClick={() => bulk('remove_from_list', filters.list_id)}>Remove from this list</Button>}
              <Button variant="secondary" onClick={() => { const t = prompt('Tag'); if (t) bulk('add_tag', t); }}>Add tag</Button>
              <Button variant="secondary" onClick={validate} loading={busy}>Validate</Button>
              <Button variant="danger" onClick={() => bulk('delete')}>Delete</Button>
            </div>
          )}
          <Table columns={leadCols} rows={data.leads} empty="No leads yet: use the Business Finder or Add lead" />
        </Card>
      )}

      {tab === 'lists' && (
        <div className="grid gap-6 md:grid-cols-[1fr_320px]">
          <Card title="Your lists">
            {!lists.length ? <Empty title="No lists yet" text="Create lists like 'Hot leads Dubai' or 'Dentists - follow up'" /> : (
              <div className="grid gap-3 md:grid-cols-2">
                {lists.map((l) => (
                  <div key={l.id} className="rounded-xl border border-slate-100 p-4 dark:border-white/[0.05]" style={{ borderLeft: `4px solid ${l.color}` }}>
                    <p className="font-bold text-slate-900 dark:text-white">{l.name}</p>
                    <p className="text-xs text-slate-500">{l.description || ''}</p>
                    <p className="mt-2 text-sm"><b>{l.count}</b> leads</p>
                    <div className="mt-3 flex gap-2">
                      <Button variant="secondary" onClick={() => { setFilters({ ...filters, list_id: l.id }); setTab('leads'); }}>Open</Button>
                      <Button variant="ghost" onClick={() => renameList(l)}>Rename</Button>
                      <Button variant="ghost" onClick={() => deleteList(l)}>Delete</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <Card title="New list">
            <form onSubmit={createList} className="space-y-3">
              <Input label="Name" required value={newList.name} onChange={(e) => setNewList({ ...newList, name: e.target.value })} />
              <Input label="Description" value={newList.description} onChange={(e) => setNewList({ ...newList, description: e.target.value })} />
              <Input label="Colour" type="color" value={newList.color} onChange={(e) => setNewList({ ...newList, color: e.target.value })} />
              <Button>Create list</Button>
            </form>
          </Card>
        </div>
      )}

      {tab === 'validate' && (
        <Card title="Validation filter" actions={<span className="text-xs text-slate-400">{ids.length ? `${ids.length} selected leads` : 'All leads in this workspace'}</span>}>
          <p className="mb-4 text-sm text-slate-600 dark:text-[#C8C4E8]">Checks email syntax, disposable/placeholder domains and MX records, normalises phone numbers to E.164 and pings each website. Runs as a background job.</p>
          <div className="mb-4 flex flex-wrap gap-5">
            <Toggle label="Check MX records (DNS)" checked={val.check_mx} onChange={(v) => setVal({ ...val, check_mx: v })} />
            <Toggle label="Check websites respond" checked={val.check_website} onChange={(v) => setVal({ ...val, check_website: v })} />
          </div>
          <Button onClick={validate} loading={busy}>Run validation</Button>
          {valRes && (
            <div className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                {Object.entries(valRes.summary).map(([k, v]) => <Stat key={k} label={k.replace(/_/g, ' ')} value={v} />)}
              </div>
              <Table rows={valRes.results} columns={[{ label: 'Lead', key: 'business_name' },
                { label: 'Email', render: (r) => <span><Badge color={statusColor(r.email.status)}>{r.email.status}</Badge> <span className="text-xs">{r.email.reason}</span></span> },
                { label: 'Phone', render: (r) => <span><Badge color={statusColor(r.phone.status)}>{r.phone.status}</Badge> <span className="text-xs">{r.phone.e164 || r.phone.reason}</span></span> },
                { label: 'Website', render: (r) => <Badge color={statusColor(r.website.status)}>{r.website.status}{r.website.http_code ? ` ${r.website.http_code}` : ''}</Badge> },
                { label: 'Score', key: 'score' }]} />
            </div>
          )}
        </Card>
      )}

      {tab === 'duplicates' && (
        <Card title={dups ? `${dups.group_count} duplicate groups · ${dups.duplicate_leads} extra leads` : 'Duplicate check'} actions={<Button variant="secondary" onClick={loadDups}>Re-scan</Button>}>
          {!dups?.groups?.length ? <Empty title="No duplicates found" text="Leads are matched on website domain, email, phone and name + city" /> : (
            <div className="space-y-4">
              {dups.groups.map((g, i) => (
                <div key={i} className="rounded-xl border border-amber-200 p-4 dark:border-amber-500/20">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm">Matched on: {g.matched_on.map((m) => <Badge key={m} color="amber">{m}</Badge>)}</span>
                    <Button onClick={() => merge(g)}>Merge into suggested</Button>
                  </div>
                  {g.leads.map((l) => (
                    <p key={l.id} className="text-sm">{l.id === g.keep_suggestion ? '★ ' : '• '}<b>{l.business_name}</b> · {l.website || '-'} · {l.email || '-'} · {l.phone || '-'} · {l.city || '-'}</p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Modal open={!!edit} onClose={() => setEdit(null)} title="Edit lead" wide>
        {edit && (
          <form onSubmit={saveEdit} className="grid gap-3 md:grid-cols-2">
            {['business_name', 'website', 'email', 'phone', 'whatsapp_number', 'linkedin_url', 'city', 'country', 'category', 'address'].map((k) => (
              <Input key={k} label={k.replace(/_/g, ' ')} value={edit[k] || ''} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} />
            ))}
            <Select label="Stage" value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })} options={STATUSES} />
            <Select label="Priority" value={edit.priority} onChange={(e) => setEdit({ ...edit, priority: e.target.value })} options={['high', 'medium', 'low']} />
            <Input className="md:col-span-2" label="Tags (comma separated)" value={edit.tags || ''} onChange={(e) => setEdit({ ...edit, tags: e.target.value })} />
            <Textarea className="md:col-span-2" label="Notes" value={edit.notes || ''} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} />
            <div className="flex gap-2 md:col-span-2"><Button>Save</Button><Button type="button" variant="ghost" onClick={() => setEdit(null)}>Cancel</Button></div>
          </form>
        )}
      </Modal>

      <Modal open={!!add} onClose={() => setAdd(null)} title="Add a lead manually" wide>
        {add && (
          <form onSubmit={saveNew} className="grid gap-3 md:grid-cols-2">
            {Object.keys(blank).filter((k) => k !== 'notes').map((k) => (
              <Input key={k} label={k.replace(/_/g, ' ')} required={k === 'business_name'} value={add[k]} onChange={(e) => setAdd({ ...add, [k]: e.target.value })} />
            ))}
            <Textarea className="md:col-span-2" label="Notes" value={add.notes} onChange={(e) => setAdd({ ...add, notes: e.target.value })} />
            <div className="md:col-span-2"><Button>Save lead</Button></div>
          </form>
        )}
      </Modal>

      <Modal open={!!timeline} onClose={() => setTimeline(null)} title={`Timeline · ${timeline?.business_name || ''}`} wide>
        {timeline && (!timeline.events.length ? <Empty title="No activity yet" /> : (
          <ol className="space-y-3 border-l-2 border-[#6D5DF6]/30 pl-4">
            {timeline.events.map((e, i) => (
              <li key={i}>
                <p className="text-xs text-slate-400">{fmtDate(e.at)} · {e.type.replace(/_/g, ' ')}</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white">{e.title} {e.status && <Badge color={statusColor(e.status)}>{e.status}</Badge>}</p>
                {e.detail && <p className="whitespace-pre-line text-xs text-slate-600 dark:text-[#C8C4E8]">{e.detail}</p>}
              </li>
            ))}
          </ol>
        ))}
      </Modal>
    </div>
  );
}

function Stat({ label, value, onClick, active }) {
  return (
    <button type="button" onClick={onClick} className={`rounded-xl border p-3 text-left transition ${active ? 'border-[#6D5DF6] bg-violet-50 dark:bg-violet-500/10' : 'border-slate-200/80 bg-white dark:border-white/[0.06] dark:bg-white/[0.015]'}`}>
      <p className="text-xs font-bold capitalize text-slate-500 dark:text-[#8E8BA3]">{label}</p>
      <p className="text-2xl font-extrabold text-slate-900 dark:text-white">{value}</p>
    </button>
  );
}
