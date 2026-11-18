'use client';
// Module 7 - Schedule Meeting: Add Meeting Date & Time (calendar + bookable slots), Set Reminders,
// Notifications (bell in the header), Follow-up Tracker, Set Next Steps, Smart no-reply reminders, .ics export.
import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api, download, fmtDate } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, Modal, PageHeader, Select, statusColor, Tabs, Textarea } from '../components/ui';

const pad = (n) => String(n).padStart(2, '0');
const toLocalInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const dayKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function Meetings() {
  const toast = useToast();
  const params = useSearchParams();
  const [tab, setTab] = useState(params.get('tab') || 'calendar');
  const [dash, setDash] = useState(null);
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [meetings, setMeetings] = useState([]);
  const [leads, setLeads] = useState([]);
  const [form, setForm] = useState(null);
  const [slots, setSlots] = useState([]);
  const [selected, setSelected] = useState(null);
  const [complete, setComplete] = useState(null);
  const [fus, setFus] = useState({ follow_ups: [], counts: {} });
  const [fuForm, setFuForm] = useState({ title: '', due_at: '', business_id: '', channel: 'email', notes: '' });
  const [steps, setSteps] = useState([]);
  const [stepForm, setStepForm] = useState({ title: '', business_id: '', owner: '', due_date: '', stage: '' });
  const [reminder, setReminder] = useState({ minutes_before: 30, channel: 'in_app' });
  const [notes, setNotes] = useState({ unread: 0, notifications: [] });
  const loadNotes = () => api('/notifications').then(setNotes).catch(() => {});
  useEffect(() => { if (tab === 'reminders') loadNotes(); }, [tab]);

  const loadDash = () => api('/meetings/dashboard').then(setDash).catch(() => {});
  async function loadMonth() {
    const start = new Date(month); const end = new Date(month.getFullYear(), month.getMonth() + 1, 1);
    try { const d = await api('/meetings', { params: { start: start.toISOString(), end: end.toISOString() } }); setMeetings(d.meetings || []); } catch (e) { toast(e.message, 'error'); }
  }
  const loadFus = () => api('/follow-ups').then(setFus).catch(() => {});
  const loadSteps = () => api('/next-steps', { params: { include_done: true } }).then((d) => setSteps(d.next_steps || [])).catch(() => {});
  useEffect(() => { loadDash(); loadFus(); loadSteps(); api('/leads', { params: { per_page: 500 } }).then((d) => setLeads(d.leads || [])).catch(() => {}); }, []);
  useEffect(() => { loadMonth(); }, [month]);

  const byDay = useMemo(() => {
    const m = {}; meetings.forEach((x) => { const k = dayKey(new Date(x.start_at)); (m[k] = m[k] || []).push(x); }); return m;
  }, [meetings]);
  const cells = useMemo(() => {
    const first = new Date(month); const offset = (first.getDay() + 6) % 7; const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    return [...Array(offset).fill(null), ...Array.from({ length: days }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1))];
  }, [month]);

  function newMeeting(day) {
    const d = day ? new Date(day) : new Date(); if (day) d.setHours(10, 0, 0, 0); else d.setHours(d.getHours() + 1, 0, 0, 0);
    setForm({ title: 'Discovery call', start: toLocalInput(d), duration_minutes: 30, business_id: params.get('business_id') || '', attendee_name: '', attendee_email: '', attendee_phone: '', location: '', meeting_link: '', notes: '', reminders: [60, 15] });
    loadSlots(dayKey(d), 30);
  }
  async function loadSlots(day, duration) {
    try { const r = await api('/meetings/slots', { params: { day, duration_minutes: duration, tz_offset_minutes: new Date().getTimezoneOffset() * -1 } }); setSlots(r.slots || []); } catch { setSlots([]); }
  }
  async function saveMeeting(e) {
    e.preventDefault();
    try {
      const body = { title: form.title, start_at: new Date(form.start).toISOString(), duration_minutes: Number(form.duration_minutes), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        business_id: form.business_id || undefined, attendee_name: form.attendee_name || undefined, attendee_email: form.attendee_email || undefined, attendee_phone: form.attendee_phone || undefined,
        location: form.location || undefined, meeting_link: form.meeting_link || undefined, notes: form.notes || undefined,
        reminders: form.reminders.map((m) => ({ minutes_before: Number(m), channel: 'in_app' })) };
      await api('/meetings', { method: 'POST', body }); toast('Meeting booked, reminders set', 'success'); setForm(null); loadMonth(); loadDash();
    } catch (err) { toast(err.message, 'error'); }
  }
  async function addReminder() {
    try { await api(`/meetings/${selected.id}/reminders`, { method: 'POST', body: { ...reminder, minutes_before: Number(reminder.minutes_before) } });
      setSelected(await api(`/meetings/${selected.id}`)); toast('Reminder added', 'success'); } catch (e) { toast(e.message, 'error'); }
  }
  async function delReminder(r) {
    try { await api(`/meetings/reminders/${r.id}`, { method: 'DELETE' }); setSelected(await api(`/meetings/${selected.id}`)); } catch (e) { toast(e.message, 'error'); }
  }
  async function cancelMeeting(m) {
    if (!confirm('Cancel this meeting?')) return;
    try { await api(`/meetings/${m.id}`, { method: 'PUT', body: { status: 'cancelled' } }); setSelected(null); loadMonth(); loadDash(); } catch (e) { toast(e.message, 'error'); }
  }
  async function submitComplete(e) {
    e.preventDefault();
    try {
      await api(`/meetings/${complete.id}/complete`, { method: 'POST', body: { status: complete.status, outcome: complete.outcome,
        next_steps: complete.next_steps.split('\n').map((s) => s.trim()).filter(Boolean), follow_up_in_days: complete.follow_up_in_days ? Number(complete.follow_up_in_days) : null } });
      toast('Outcome saved; next steps and follow-up created', 'success'); setComplete(null); setSelected(null); loadMonth(); loadDash(); loadFus(); loadSteps();
    } catch (err) { toast(err.message, 'error'); }
  }
  async function addFu(e) {
    e.preventDefault();
    try { await api('/follow-ups', { method: 'POST', body: { ...fuForm, due_at: new Date(fuForm.due_at).toISOString(), business_id: fuForm.business_id || undefined } });
      setFuForm({ title: '', due_at: '', business_id: '', channel: 'email', notes: '' }); loadFus(); loadDash(); } catch (err) { toast(err.message, 'error'); }
  }
  async function fuUpdate(f, body) { try { await api(`/follow-ups/${f.id}`, { method: 'PUT', body }); loadFus(); loadDash(); } catch (e) { toast(e.message, 'error'); } }
  async function addStep(e) {
    e.preventDefault();
    try { await api('/next-steps', { method: 'POST', body: { ...stepForm, business_id: stepForm.business_id || undefined, due_date: stepForm.due_date || undefined } });
      setStepForm({ title: '', business_id: '', owner: '', due_date: '', stage: '' }); loadSteps(); } catch (err) { toast(err.message, 'error'); }
  }
  async function stepToggle(s) { try { await api(`/next-steps/${s.id}`, { method: 'PUT', body: { done: !s.done } }); loadSteps(); } catch (e) { toast(e.message, 'error'); } }
  async function stepDel(s) { try { await api(`/next-steps/${s.id}`, { method: 'DELETE' }); loadSteps(); } catch (e) { toast(e.message, 'error'); } }
  async function runChecks() {
    try { const r = await api('/meetings/reminders/run-due', { method: 'POST' }); toast(`${r.delivered} reminders delivered, ${r.no_reply_alerts} no-reply alerts`, 'info'); loadFus(); loadDash(); } catch (e) { toast(e.message, 'error'); }
  }

  const leadOpts = [{ value: '', label: 'No lead' }, ...leads.map((l) => ({ value: l.id, label: l.business_name }))];
  const counts = fus.counts || {};

  return (
    <div className="space-y-6">
      <PageHeader module="[7] Schedule Meeting" title="Schedule Meeting"
        subtitle="Book meetings, get reminded, never forget a follow-up. Leads that don't reply get a follow-up task automatically."
        actions={<><Button variant="secondary" onClick={runChecks}>Run reminder check</Button><Button onClick={() => newMeeting()}>New meeting</Button></>} />

      {dash && (
        <div className="grid gap-3 md:grid-cols-4">
          <Mini label="Upcoming meetings" value={dash.upcoming_meetings.length} />
          <Mini label="Overdue follow-ups" value={dash.follow_ups.overdue.length} danger={dash.follow_ups.overdue.length > 0} />
          <Mini label="Due today" value={dash.follow_ups.today.length} />
          <Mini label="Open next steps" value={dash.next_steps.length} />
        </div>
      )}

      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'calendar', label: 'Add Meeting Date & Time' }, { id: 'reminders', label: 'Set Reminders & Notifications' }, { id: 'followups', label: `Follow-up Tracker (${(counts.overdue || 0) + (counts.today || 0) + (counts.upcoming || 0)})` }, { id: 'steps', label: 'Set Next Steps' }]} />

      {tab === 'calendar' && (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card title={month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
            actions={<div className="flex gap-1"><Button variant="secondary" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>‹</Button>
              <Button variant="secondary" onClick={() => { const d = new Date(); setMonth(new Date(d.getFullYear(), d.getMonth(), 1)); }}>Today</Button>
              <Button variant="secondary" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>›</Button></div>}>
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-bold text-slate-400">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => <div key={d}>{d}</div>)}</div>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {cells.map((d, i) => d ? (
                <button key={i} onClick={() => newMeeting(d)} className={`min-h-[84px] rounded-lg border p-1 text-left align-top transition hover:border-[#6D5DF6] ${dayKey(d) === dayKey(new Date()) ? 'border-[#6D5DF6]' : 'border-slate-100 dark:border-white/[0.05]'}`}>
                  <span className="text-xs font-bold text-slate-500">{d.getDate()}</span>
                  {(byDay[dayKey(d)] || []).map((m) => (
                    <div key={m.id} onClick={(e) => { e.stopPropagation(); setSelected(m); }}
                      className={`mt-0.5 truncate rounded px-1 text-[10px] font-bold text-white ${m.status === 'cancelled' ? 'bg-slate-400 line-through' : m.status === 'completed' ? 'bg-emerald-500' : 'bg-[#6D5DF6]'}`}>
                      {new Date(m.start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} {m.business_name || m.title}
                    </div>
                  ))}
                </button>) : <div key={i} />)}
            </div>
            <p className="mt-2 text-xs text-slate-400">Click a day to book; click a meeting to see details, reminders and the .ics file.</p>
          </Card>
          <Card title="Upcoming">
            {!dash?.upcoming_meetings?.length ? <Empty title="No upcoming meetings" /> : dash.upcoming_meetings.map((m) => (
              <button key={m.id} onClick={() => setSelected(m)} className="mb-2 block w-full rounded-lg border border-slate-100 p-3 text-left text-sm hover:border-[#6D5DF6] dark:border-white/[0.05]">
                <p className="font-bold text-slate-900 dark:text-white">{m.title}</p><p className="text-xs text-slate-500">{fmtDate(m.start_at)}{m.business_name ? ` · ${m.business_name}` : ''}</p>
              </button>
            ))}
          </Card>
        </div>
      )}

      {tab === 'reminders' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Set Reminders" actions={<Button variant="secondary" onClick={() => { runChecks(); loadNotes(); }}>Run check now</Button>}>
            {!dash?.upcoming_meetings?.length ? <Empty title="No upcoming meetings" text="Reminders are set when you book a meeting" /> : dash.upcoming_meetings.map((m) => (
              <div key={m.id} className="mb-3 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05]">
                <div className="flex items-center justify-between"><b className="text-slate-900 dark:text-white">{m.title}{m.business_name ? ` · ${m.business_name}` : ''}</b>
                  <Button variant="ghost" onClick={() => setSelected(m)}>Edit reminders</Button></div>
                <p className="text-xs text-slate-500">{fmtDate(m.start_at)}</p>
                <div className="mt-1 flex flex-wrap gap-1">{(m.reminders || []).map((r) => <Badge key={r.id} color={r.sent ? 'green' : 'blue'}>{r.channel} · {fmtDate(r.remind_at)}{r.sent ? ' ✓' : ''}</Badge>)}</div>
              </div>
            ))}
            <p className="mt-2 text-xs text-slate-400">Smart reminders: if a contacted lead doesn&apos;t reply within the days set in Workspace settings, a follow-up task and an alert are created automatically (Celery beat every 15 min).</p>
          </Card>
          <Card title={`Notifications (${notes.unread} unread)`} actions={<Button variant="ghost" onClick={async () => { await api('/notifications/read-all', { method: 'POST' }).catch(() => {}); loadNotes(); }}>Mark all read</Button>}>
            {!notes.notifications.length ? <Empty title="No notifications yet" /> : notes.notifications.map((n) => (
              <div key={n.id} className={`mb-2 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05] ${n.read ? 'opacity-60' : ''}`}>
                <p className="font-bold text-slate-900 dark:text-white">{n.title}</p>{n.body && <p className="text-xs text-slate-600 dark:text-[#C8C4E8]">{n.body}</p>}
                <p className="text-[10px] text-slate-400">{fmtDate(n.created_at)}</p>
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === 'followups' && (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card title="Follow-up tracker">
            {['overdue', 'today', 'upcoming', 'done'].map((b) => {
              const items = fus.follow_ups.filter((f) => f.bucket === b);
              if (!items.length) return null;
              return (
                <div key={b} className="mb-5">
                  <p className="mb-2 text-xs font-bold uppercase text-slate-500"><Badge color={statusColor(b)}>{b}</Badge> {items.length}</p>
                  {items.map((f) => (
                    <div key={f.id} className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05]">
                      <div><p className={`font-bold text-slate-900 dark:text-white ${f.status === 'done' ? 'line-through opacity-60' : ''}`}>{f.title}</p>
                        <p className="text-xs text-slate-500">{fmtDate(f.due_at)} · {f.channel}{f.business_name ? ` · ${f.business_name}` : ''}</p>{f.notes && <p className="text-xs text-slate-400">{f.notes}</p>}</div>
                      {f.status !== 'done' && <div className="flex gap-1"><Button variant="success" onClick={() => fuUpdate(f, { status: 'done' })}>Done</Button>
                        <Button variant="secondary" onClick={() => fuUpdate(f, { snooze_days: 1 })}>+1 day</Button><Button variant="secondary" onClick={() => fuUpdate(f, { snooze_days: 3 })}>+3 days</Button></div>}
                    </div>
                  ))}
                </div>
              );
            })}
            {!fus.follow_ups.length && <Empty title="No follow-ups" text="They're created when you complete a meeting, when a lead doesn't reply, or manually" />}
          </Card>
          <Card title="Add follow-up">
            <form onSubmit={addFu} className="space-y-3">
              <Input label="Title" required value={fuForm.title} onChange={(e) => setFuForm({ ...fuForm, title: e.target.value })} />
              <Input label="Due" type="datetime-local" required value={fuForm.due_at} onChange={(e) => setFuForm({ ...fuForm, due_at: e.target.value })} />
              <Select label="Lead" value={fuForm.business_id} onChange={(e) => setFuForm({ ...fuForm, business_id: e.target.value })} options={leadOpts} />
              <Select label="Channel" value={fuForm.channel} onChange={(e) => setFuForm({ ...fuForm, channel: e.target.value })} options={['email', 'whatsapp', 'linkedin', 'call']} />
              <Textarea label="Notes" rows={2} value={fuForm.notes} onChange={(e) => setFuForm({ ...fuForm, notes: e.target.value })} />
              <Button>Add</Button>
            </form>
          </Card>
        </div>
      )}

      {tab === 'steps' && (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card title="Next steps">
            {!steps.length ? <Empty title="No next steps yet" /> : steps.map((s) => (
              <div key={s.id} className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05]">
                <label className="flex items-center gap-3"><input type="checkbox" className="h-4 w-4 accent-[#6D5DF6]" checked={s.done} onChange={() => stepToggle(s)} />
                  <span><span className={`font-bold text-slate-900 dark:text-white ${s.done ? 'line-through opacity-60' : ''}`}>{s.title}</span>
                    <span className="block text-xs text-slate-500">{[s.business_name, s.owner && `owner: ${s.owner}`, s.due_date && `due ${s.due_date}`, s.stage].filter(Boolean).join(' · ')}</span></span></label>
                <Button variant="ghost" onClick={() => stepDel(s)}>Delete</Button>
              </div>
            ))}
          </Card>
          <Card title="Add next step">
            <form onSubmit={addStep} className="space-y-3">
              <Input label="What happens next" required value={stepForm.title} onChange={(e) => setStepForm({ ...stepForm, title: e.target.value })} placeholder="Send proposal" />
              <Select label="Lead" value={stepForm.business_id} onChange={(e) => setStepForm({ ...stepForm, business_id: e.target.value })} options={leadOpts} />
              <Input label="Owner" value={stepForm.owner} onChange={(e) => setStepForm({ ...stepForm, owner: e.target.value })} />
              <Input label="Due date" type="date" value={stepForm.due_date} onChange={(e) => setStepForm({ ...stepForm, due_date: e.target.value })} />
              <Select label="Pipeline stage" value={stepForm.stage} onChange={(e) => setStepForm({ ...stepForm, stage: e.target.value })} options={['', 'proposal', 'negotiation', 'contract', 'onboarding', 'won', 'lost']} />
              <Button>Add</Button>
            </form>
          </Card>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title="Book a meeting" wide>
        {form && (
          <form onSubmit={saveMeeting} className="grid gap-3 md:grid-cols-2">
            <Input className="md:col-span-2" label="Title" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <Input label="Start" type="datetime-local" required value={form.start} onChange={(e) => { setForm({ ...form, start: e.target.value }); loadSlots(e.target.value.slice(0, 10), form.duration_minutes); }} />
            <Select label="Duration" value={form.duration_minutes} onChange={(e) => { setForm({ ...form, duration_minutes: e.target.value }); loadSlots(form.start.slice(0, 10), e.target.value); }}
              options={[15, 30, 45, 60, 90, 120].map((m) => ({ value: m, label: `${m} minutes` }))} />
            {slots.length > 0 && (
              <div className="md:col-span-2">
                <p className="mb-1 text-xs font-bold text-slate-500">Free slots that day</p>
                <div className="flex flex-wrap gap-1">{slots.slice(0, 18).map((s) => (
                  <button type="button" key={s.start} onClick={() => setForm({ ...form, start: toLocalInput(new Date(s.start)) })}
                    className={`rounded-lg border px-2 py-1 text-xs font-bold ${toLocalInput(new Date(s.start)) === form.start ? 'border-[#6D5DF6] bg-[#6D5DF6] text-white' : 'border-slate-200 dark:border-white/10'}`}>
                    {new Date(s.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</button>))}</div>
              </div>
            )}
            <Select label="Lead" value={form.business_id} onChange={(e) => { const l = leads.find((x) => x.id === e.target.value); setForm({ ...form, business_id: e.target.value, attendee_email: l?.email || form.attendee_email, attendee_phone: l?.phone || form.attendee_phone }); }} options={leadOpts} />
            <Input label="Attendee name" value={form.attendee_name} onChange={(e) => setForm({ ...form, attendee_name: e.target.value })} />
            <Input label="Attendee email" type="email" value={form.attendee_email} onChange={(e) => setForm({ ...form, attendee_email: e.target.value })} />
            <Input label="Attendee phone" value={form.attendee_phone} onChange={(e) => setForm({ ...form, attendee_phone: e.target.value })} />
            <Input label="Location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            <Input label="Meeting link" value={form.meeting_link} onChange={(e) => setForm({ ...form, meeting_link: e.target.value })} placeholder="https://meet.google.com/..." />
            <div className="md:col-span-2">
              <p className="mb-1 text-xs font-bold text-slate-500">Reminders (minutes before)</p>
              <div className="flex flex-wrap gap-2">{[1440, 120, 60, 30, 15, 5].map((m) => (
                <button type="button" key={m} onClick={() => setForm({ ...form, reminders: form.reminders.includes(m) ? form.reminders.filter((x) => x !== m) : [...form.reminders, m] })}
                  className={`rounded-lg border px-2 py-1 text-xs font-bold ${form.reminders.includes(m) ? 'border-[#6D5DF6] bg-[#6D5DF6] text-white' : 'border-slate-200 dark:border-white/10'}`}>{m >= 60 ? `${m / 60} h` : `${m} min`}</button>))}</div>
            </div>
            <Textarea className="md:col-span-2" label="Agenda / notes" rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            <div className="md:col-span-2"><Button>Book meeting</Button></div>
          </form>
        )}
      </Modal>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected?.title || ''}>
        {selected && (
          <div className="space-y-3 text-sm">
            <p><Badge color={statusColor(selected.status)}>{selected.status}</Badge> {fmtDate(selected.start_at)} → {new Date(selected.end_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
            {selected.business_name && <p>Lead: <b>{selected.business_name}</b></p>}
            {selected.attendee_email && <p>Attendee: {selected.attendee_name} {selected.attendee_email} {selected.attendee_phone}</p>}
            {selected.location && <p>Location: {selected.location}</p>}
            {selected.meeting_link && <p>Link: <a href={selected.meeting_link} target="_blank" rel="noreferrer" className="text-[#6D5DF6]">{selected.meeting_link}</a></p>}
            {selected.notes && <p className="whitespace-pre-line text-slate-500">{selected.notes}</p>}
            {selected.outcome && <p>Outcome: {selected.outcome}</p>}
            <div>
              <p className="mb-1 text-xs font-bold text-slate-500">Reminders</p>
              {(selected.reminders || []).map((r) => <p key={r.id} className="text-xs">{fmtDate(r.remind_at)} · {r.channel} {r.sent ? <Badge color="green">sent</Badge> : <button className="text-red-500" onClick={() => delReminder(r)}>remove</button>}</p>)}
              <div className="mt-2 flex items-end gap-2">
                <Input type="number" label="Min before" value={reminder.minutes_before} onChange={(e) => setReminder({ ...reminder, minutes_before: e.target.value })} />
                <Select label="Channel" value={reminder.channel} onChange={(e) => setReminder({ ...reminder, channel: e.target.value })} options={['in_app', 'email', 'whatsapp']} />
                <Button variant="secondary" onClick={addReminder}>Add</Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="secondary" onClick={() => download(`/meetings/${selected.id}/ics`, 'meeting.ics')}>Add to calendar (.ics)</Button>
              {selected.status === 'scheduled' && <><Button onClick={() => setComplete({ id: selected.id, status: 'completed', outcome: '', next_steps: '', follow_up_in_days: 3 })}>Log outcome</Button>
                <Button variant="ghost" onClick={() => cancelMeeting(selected)}>Cancel</Button></>}
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!complete} onClose={() => setComplete(null)} title="Meeting outcome">
        {complete && (
          <form onSubmit={submitComplete} className="space-y-3">
            <Select label="Result" value={complete.status} onChange={(e) => setComplete({ ...complete, status: e.target.value })} options={['completed', 'no_show', 'cancelled']} />
            <Textarea label="What happened" rows={3} value={complete.outcome} onChange={(e) => setComplete({ ...complete, outcome: e.target.value })} />
            <Textarea label="Next steps (one per line)" rows={3} value={complete.next_steps} onChange={(e) => setComplete({ ...complete, next_steps: e.target.value })} />
            <Input label="Create a follow-up in (days, blank = none)" type="number" value={complete.follow_up_in_days ?? ''} onChange={(e) => setComplete({ ...complete, follow_up_in_days: e.target.value })} />
            <Button>Save</Button>
          </form>
        )}
      </Modal>
    </div>
  );
}

function Mini({ label, value, danger }) {
  return (
    <div className={`rounded-xl border p-4 ${danger ? 'border-red-200 bg-red-50 dark:border-red-500/20 dark:bg-red-500/10' : 'border-slate-200/80 bg-white dark:border-white/[0.06] dark:bg-white/[0.015]'}`}>
      <p className="text-xs font-bold text-slate-500 dark:text-[#8E8BA3]">{label}</p><p className="text-2xl font-extrabold text-slate-900 dark:text-white">{value}</p>
    </div>
  );
}

export default function MeetingsPage() { return <Suspense fallback={null}><Meetings /></Suspense>; }
