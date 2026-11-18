'use client';
// Module 5 - AI Copywriter: Personalized Icebreakers, Bulk Email Generation, Dynamic Reply Assistant,
// Industry-Specific Content. Groq / OpenAI / Gemini via env, template engine as fallback. Every draft is
// editable: the user reviews before anything is sent.
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { api, runJob } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, PageHeader, Select, Tabs, Textarea, Toggle, useCopy } from '../components/ui';

const TONES = ['professional', 'friendly', 'casual', 'confident', 'consultative'];
const CONTENT = { cold_email: 'Cold email', follow_up: 'Follow-up email', linkedin_note: 'LinkedIn note', whatsapp: 'WhatsApp intro', landing_copy: 'Landing page copy', social_post: 'Social post' };

function Copywriter() {
  const toast = useToast();
  const copy = useCopy();
  const params = useSearchParams();
  const [tab, setTab] = useState('icebreakers');
  const [status, setStatus] = useState(null);
  const [leads, setLeads] = useState([]);
  const [lists, setLists] = useState([]);
  const [industries, setIndustries] = useState([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');

  const [ib, setIb] = useState({ business_id: params.get('business_id') || '', count: 3, tone: 'friendly', manual: { business_name: '', website: '', city: '', category: '' } });
  const [ibRes, setIbRes] = useState(null);
  const [bulk, setBulk] = useState({ source: 'list', list_id: '', business_ids: params.get('business_id') ? [params.get('business_id')] : [], channel: 'email', tone: 'professional', industry: '', instructions: '', use_icebreaker: true });
  const [drafts, setDrafts] = useState([]);
  const [batch, setBatch] = useState('');
  const [rp, setRp] = useState({ message: '', business_id: '', instruction: '' });
  const [rpRes, setRpRes] = useState(null);
  const [ic, setIc] = useState({ industry: 'generic', content_type: 'cold_email', business_id: '', tone: 'professional' });
  const [icRes, setIcRes] = useState(null);

  useEffect(() => {
    api('/copywriter/status').then(setStatus).catch(() => {});
    api('/leads', { params: { per_page: 500 } }).then((d) => setLeads(d.leads || [])).catch(() => {});
    api('/leads/lists').then((d) => setLists(d.lists || [])).catch(() => {});
    api('/copywriter/industries').then((d) => setIndustries(d.industries || [])).catch(() => {});
    if (params.get('business_id')) setBulk((b) => ({ ...b, source: 'leads' }));
  }, []);
  useEffect(() => { if (tab === 'drafts') api('/copywriter/drafts', { params: { kind: 'email' } }).then((d) => setDrafts(d.drafts || [])).catch(() => {}); }, [tab]);

  const leadOptions = [{ value: '', label: 'Choose a saved lead...' }, ...leads.map((l) => ({ value: l.id, label: `${l.business_name}${l.city ? ' · ' + l.city : ''}` }))];

  async function genIcebreakers(e) {
    e.preventDefault(); setBusy(true);
    try {
      const body = { count: Number(ib.count), tone: ib.tone, ...(ib.business_id ? { business_id: ib.business_id } : { lead: ib.manual }) };
      setIbRes(await api('/copywriter/icebreakers', { method: 'POST', body }));
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); }
  }
  async function genBulk(e) {
    e.preventDefault(); setBusy(true); setDrafts([]);
    try {
      const body = { channel: bulk.channel, tone: bulk.tone, industry: bulk.industry || undefined, instructions: bulk.instructions, use_icebreaker: bulk.use_icebreaker,
        ...(bulk.source === 'list' ? { list_id: bulk.list_id } : { business_ids: bulk.business_ids }) };
      const r = await runJob('bulk_copy', body, { onStatus: (j) => setProgress(`Writing personalised messages... (${j.status}, ${j.runner || 'queued'})`) });
      setDrafts(r.drafts || []); setBatch(r.batch_id); toast(`${r.count} drafts ready: review and edit below`, 'success');
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); setProgress(''); }
  }
  async function saveDraft(d) {
    try { await api(`/copywriter/drafts/${d.id}`, { method: 'PUT', body: { subject: d.subject, body: d.body } }); toast('Draft saved', 'success'); } catch (e) { toast(e.message, 'error'); }
  }
  async function delDraft(d) {
    try { await api(`/copywriter/drafts/${d.id}`, { method: 'DELETE' }); setDrafts(drafts.filter((x) => x.id !== d.id)); } catch (e) { toast(e.message, 'error'); }
  }
  async function genReply(e) {
    e.preventDefault(); setBusy(true);
    try { setRpRes(await api('/copywriter/reply', { method: 'POST', body: { ...rp, business_id: rp.business_id || undefined } })); } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); }
  }
  async function genContent(e) {
    e.preventDefault(); setBusy(true);
    try { setIcRes(await api('/copywriter/industry-content', { method: 'POST', body: { ...ic, business_id: ic.business_id || undefined } })); } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); }
  }
  const copyIt = async (t) => toast((await copy(t)) ? 'Copied' : 'Copy failed', 'info');
  const leadName = (id) => leads.find((l) => l.id === id)?.business_name || 'Lead';

  return (
    <div className="space-y-6">
      <PageHeader module="[5] AI Copywriter" title="AI Copywriter"
        subtitle="Personalised outreach written from each lead's own website audit. You review and edit every message before it goes out."
        actions={status && <Badge color={status.llm_available ? 'green' : 'amber'}>{status.llm_available ? `AI: ${status.provider}${status.model ? ' · ' + status.model : ''}` : 'Template mode (add GROQ_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY for AI)'}</Badge>} />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'icebreakers', label: 'Personalized Icebreakers' }, { id: 'bulk', label: 'Bulk Email Generation' },
        { id: 'reply', label: 'Dynamic Reply Assistant' }, { id: 'industry', label: 'Industry-Specific Content' }, { id: 'drafts', label: 'Saved drafts' }]} />

      {tab === 'icebreakers' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Personalised icebreakers">
            <form onSubmit={genIcebreakers} className="space-y-3">
              <Select label="Lead" value={ib.business_id} onChange={(e) => setIb({ ...ib, business_id: e.target.value })} options={leadOptions} />
              {!ib.business_id && (
                <div className="grid gap-3 md:grid-cols-2">
                  {['business_name', 'website', 'city', 'category'].map((k) => <Input key={k} label={k.replace('_', ' ')} value={ib.manual[k]} onChange={(e) => setIb({ ...ib, manual: { ...ib.manual, [k]: e.target.value } })} required={k === 'business_name'} />)}
                </div>
              )}
              <div className="grid gap-3 md:grid-cols-2">
                <Select label="Tone" value={ib.tone} onChange={(e) => setIb({ ...ib, tone: e.target.value })} options={TONES} />
                <Input label="How many" type="number" min="1" max="10" value={ib.count} onChange={(e) => setIb({ ...ib, count: e.target.value })} />
              </div>
              <Button loading={busy}>Generate</Button>
            </form>
          </Card>
          <Card title="Results">
            {!ibRes ? <Empty title="Pick a lead and generate" text="Uses the lead's latest audit findings when available" /> : (
              <div className="space-y-3">
                {ibRes.deduction && (
                  <div className="rounded-lg bg-violet-50 p-3 text-sm dark:bg-violet-500/10">
                    <p className="font-bold text-violet-800 dark:text-violet-200">AI deduction</p>
                    <p><b>Pain point:</b> {ibRes.deduction.pain_point}</p>
                    <p><b>Pitch:</b> {ibRes.deduction.recommended_service} → {ibRes.deduction.outcome}</p>
                  </div>
                )}
                {ibRes.icebreakers.map((t) => (
                  <div key={t} className="flex items-start justify-between gap-2 rounded-lg border border-slate-100 p-3 text-sm dark:border-white/[0.05]">
                    <p className="text-slate-800 dark:text-white">{t}</p><Button variant="ghost" onClick={() => copyIt(t)}>Copy</Button>
                  </div>
                ))}
                <p className="text-xs text-slate-400">Source: {ibRes.source} · industry: {ibRes.industry}</p>
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'bulk' && (
        <>
          <Card title="Generate personalised messages for many leads">
            <form onSubmit={genBulk} className="grid gap-3 md:grid-cols-3">
              <Select label="Leads from" value={bulk.source} onChange={(e) => setBulk({ ...bulk, source: e.target.value })} options={[{ value: 'list', label: 'A lead list' }, { value: 'leads', label: 'Pick leads' }]} />
              {bulk.source === 'list'
                ? <Select className="md:col-span-2" label="List" value={bulk.list_id} onChange={(e) => setBulk({ ...bulk, list_id: e.target.value })} options={[{ value: '', label: 'Choose a list...' }, ...lists.map((l) => ({ value: l.id, label: `${l.name} (${l.count})` }))]} />
                : <div className="md:col-span-2">
                    <span className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-[#C8C4E8]">Leads ({bulk.business_ids.length} selected)</span>
                    <div className="max-h-40 overflow-y-auto rounded-xl border border-slate-200 p-2 dark:border-white/10">
                      {leads.map((l) => (
                        <label key={l.id} className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-[#6D5DF6]" checked={bulk.business_ids.includes(l.id)}
                          onChange={(e) => setBulk({ ...bulk, business_ids: e.target.checked ? [...bulk.business_ids, l.id] : bulk.business_ids.filter((x) => x !== l.id) })} />{l.business_name}</label>
                      ))}
                    </div>
                  </div>}
              <Select label="Channel" value={bulk.channel} onChange={(e) => setBulk({ ...bulk, channel: e.target.value })} options={['email', 'linkedin', 'whatsapp']} />
              <Select label="Tone" value={bulk.tone} onChange={(e) => setBulk({ ...bulk, tone: e.target.value })} options={TONES} />
              <Select label="Industry" value={bulk.industry} onChange={(e) => setBulk({ ...bulk, industry: e.target.value })} options={[{ value: '', label: 'Auto-detect per lead' }, ...industries.map((i) => ({ value: i.key, label: i.label }))]} />
              <Textarea className="md:col-span-3" rows={2} label="Extra instructions (optional)" value={bulk.instructions} onChange={(e) => setBulk({ ...bulk, instructions: e.target.value })} placeholder="Mention our 7-day delivery and free audit report" />
              <Toggle label="Open with a personalised icebreaker" checked={bulk.use_icebreaker} onChange={(v) => setBulk({ ...bulk, use_icebreaker: v })} />
              <div className="md:col-span-2 md:text-right"><Button loading={busy}>Generate drafts</Button></div>
            </form>
            {progress && <p className="mt-3 text-sm text-[#6D5DF6]">{progress}</p>}
          </Card>
          {drafts.length > 0 && <DraftList drafts={drafts} setDrafts={setDrafts} saveDraft={saveDraft} delDraft={delDraft} leadName={leadName} batch={batch} />}
        </>
      )}

      {tab === 'reply' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Dynamic reply assistant">
            <form onSubmit={genReply} className="space-y-3">
              <Textarea label="Their message" rows={6} required value={rp.message} onChange={(e) => setRp({ ...rp, message: e.target.value })} placeholder="Paste the prospect's reply..." />
              <Select label="Lead (optional, for context)" value={rp.business_id} onChange={(e) => setRp({ ...rp, business_id: e.target.value })} options={leadOptions} />
              <Input label="What do you want to achieve? (optional)" value={rp.instruction} onChange={(e) => setRp({ ...rp, instruction: e.target.value })} placeholder="Book a call this week" />
              <Button loading={busy}>Suggest replies</Button>
            </form>
          </Card>
          <Card title="Suggestions">
            {!rpRes ? <Empty title="Paste a reply to get suggestions" /> : (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2"><Badge color="blue">intent: {rpRes.intent}</Badge><Badge color={rpRes.sentiment === 'negative' ? 'red' : rpRes.sentiment === 'positive' ? 'green' : 'gray'}>{rpRes.sentiment}</Badge>
                  {rpRes.next_action && <Badge color="purple">next: {rpRes.next_action}</Badge>}</div>
                {rpRes.suggested_replies.map((s) => (
                  <div key={s.label} className="rounded-lg border border-slate-100 p-3 dark:border-white/[0.05]">
                    <div className="mb-1 flex justify-between"><b className="text-sm text-slate-900 dark:text-white">{s.label}</b><Button variant="ghost" onClick={() => copyIt(s.body)}>Copy</Button></div>
                    <p className="whitespace-pre-line text-sm text-slate-700 dark:text-[#C8C4E8]">{s.body}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'industry' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Industry-specific content">
            <form onSubmit={genContent} className="space-y-3">
              <Select label="Industry" value={ic.industry} onChange={(e) => setIc({ ...ic, industry: e.target.value })} options={industries.map((i) => ({ value: i.key, label: i.label }))} />
              <Select label="Content type" value={ic.content_type} onChange={(e) => setIc({ ...ic, content_type: e.target.value })} options={Object.entries(CONTENT).map(([value, label]) => ({ value, label }))} />
              <Select label="Personalise for a lead (optional)" value={ic.business_id} onChange={(e) => setIc({ ...ic, business_id: e.target.value })} options={[{ value: '', label: 'Reusable template' }, ...leadOptions.slice(1)]} />
              <Select label="Tone" value={ic.tone} onChange={(e) => setIc({ ...ic, tone: e.target.value })} options={TONES} />
              <Button loading={busy}>Write</Button>
            </form>
            {industries.find((i) => i.key === ic.industry) && (
              <div className="mt-4 text-xs text-slate-500 dark:text-[#8E8BA3]">
                <p><b>Typical pains:</b> {industries.find((i) => i.key === ic.industry).pains.join('; ')}</p>
                <p><b>What to offer:</b> {industries.find((i) => i.key === ic.industry).offers.join('; ')}</p>
              </div>
            )}
          </Card>
          <Card title={icRes?.title || 'Output'} actions={icRes && <Button variant="ghost" onClick={() => copyIt(icRes.body)}>Copy</Button>}>
            {!icRes ? <Empty title="Choose an industry and content type" /> : <Textarea rows={16} value={icRes.body} onChange={(e) => setIcRes({ ...icRes, body: e.target.value })} />}
          </Card>
        </div>
      )}

      {tab === 'drafts' && (drafts.length ? <DraftList drafts={drafts} setDrafts={setDrafts} saveDraft={saveDraft} delDraft={delDraft} leadName={leadName} /> : <Empty title="No email drafts yet" text="Generate some in Bulk email generation" />)}
    </div>
  );
}

function DraftList({ drafts, setDrafts, saveDraft, delDraft, leadName, batch }) {
  const upd = (id, k, v) => setDrafts(drafts.map((d) => (d.id === id ? { ...d, [k]: v } : d)));
  return (
    <Card title={`${drafts.length} drafts`} actions={batch && drafts[0]?.channel === 'email' && <Link href={`/channels?batch_id=${batch}`}><Button>Review & send batch →</Button></Link>}>
      <div className="space-y-4">
        {drafts.map((d) => (
          <div key={d.id} className="rounded-xl border border-slate-100 p-4 dark:border-white/[0.05]">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-bold text-slate-900 dark:text-white">{leadName(d.business_id)} <Badge>{d.channel}</Badge> <Badge color="purple">{d.industry}</Badge></span>
              <span className="flex gap-1"><Button variant="secondary" onClick={() => saveDraft(d)}>Save</Button><Button variant="ghost" onClick={() => delDraft(d)}>Delete</Button></span>
            </div>
            {d.channel === 'email' && <Input value={d.subject || ''} onChange={(e) => upd(d.id, 'subject', e.target.value)} placeholder="Subject" />}
            <Textarea className="mt-2" rows={7} value={d.body || ''} onChange={(e) => upd(d.id, 'body', e.target.value)} />
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function CopywriterPage() { return <Suspense fallback={null}><Copywriter /></Suspense>; }
