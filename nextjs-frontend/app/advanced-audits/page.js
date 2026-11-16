'use client';
// Module 4 - Advanced Audit: Speed & Security Audit, Tech Stack Detection, Mobile Friendliness Score,
// Competitor Benchmarking + SEO indexing checks and the Trust & Conversion Leak Detector.
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { api, fmtDate, runJob } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, PageHeader, ScoreRing, Table, Tabs, Textarea, Toggle } from '../components/ui';

// Turns any value (text, number, list, object) into safe text for React
const txt = (v) => {
  if (v == null) return '-';
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.map(txt).join(', ');
  if (typeof v === 'object') {
    if (v.header) return v.value ? `${v.header}: ${v.value}` : String(v.header);
    return String(v.message || v.name || v.title || v.tip || JSON.stringify(v));
  }
  return String(v);
};

function Audits() {
  const toast = useToast();
  const params = useSearchParams();
  const [tab, setTab] = useState('speed');
  const [url, setUrl] = useState('');
  const [businessId, setBusinessId] = useState(params.get('business_id') || '');
  const [lead, setLead] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [history, setHistory] = useState([]);
  const [bm, setBm] = useState({ target_url: '', competitors: '', auto_find: false, category: '', city: '' });
  const [bmRes, setBmRes] = useState(null);
  const [benchmarks, setBenchmarks] = useState([]);

  const loadHistory = () => {
    api('/advanced-audits').then((d) => setHistory(d.audits || [])).catch(() => {});
    api('/advanced-audits/benchmarks').then((d) => setBenchmarks(d.benchmarks || [])).catch(() => {});
  };
  useEffect(() => {
    loadHistory();
    if (businessId) {
      api('/leads', { params: { per_page: 500 } }).then((d) => {
        const l = d.leads.find((x) => x.id === businessId);
        if (l) { setLead(l); setUrl(l.website || ''); setBm((b) => ({ ...b, target_url: l.website || '', category: l.category || '', city: l.city || '' })); }
      }).catch(() => {});
    }
  }, []);

  async function run(e) {
    e?.preventDefault();
    setBusy(true); setReport(null);
    try {
      const r = await runJob('advanced_audit', businessId && lead?.website === url ? { business_id: businessId } : { url },
        { onStatus: (j) => setStatus(`Auditing speed, security, tech, mobile, SEO and trust... (${j.status})`) });
      setReport(r); loadHistory();
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); setStatus(''); }
  }
  async function open(a) {
    try { setReport(await api(`/advanced-audits/${a.id}`).then((d) => ({ id: d.id, ...(d.report || d) }))); setTab('speed'); } catch (e) { toast(e.message, 'error'); }
  }
  async function runBm(e) {
    e.preventDefault(); setBusy(true); setBmRes(null);
    try {
      const r = await runJob('benchmark', { target_url: bm.target_url, competitor_urls: bm.competitors.split(/[\s,]+/).filter(Boolean),
        auto_find: bm.auto_find, category: bm.category || undefined, city: bm.city || undefined },
        { onStatus: (j) => setStatus(`Auditing target and competitors... (${j.status})`) });
      setBmRes(r); loadHistory();
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); setStatus(''); }
  }

  return (
    <div className="space-y-6">
      <PageHeader module="[4] Advanced Audit" title="Advanced Audit"
        subtitle="Speed, SSL & security headers, tech stack (with outdated versions), mobile friendliness, Google indexing and trust & conversion leaks." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'speed', label: 'Speed & Security Audit' }, { id: 'tech', label: 'Tech Stack Detection' }, { id: 'benchmark', label: 'Competitor Benchmarking' },
        { id: 'mobile', label: 'Mobile Friendliness Score' }, { id: 'history', label: `History (${history.length})` }]} />

      {['speed', 'tech', 'mobile'].includes(tab) && (
        <>
          <Card>
            <form onSubmit={run} className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
              <Input label={lead ? `Website of ${lead.business_name}` : 'Website URL'} required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://business.com" />
              <Button loading={busy}>Run audit</Button>
            </form>
            {status && <p className="mt-3 text-sm text-[#6D5DF6]">{status}</p>}
          </Card>
          {report && <Report r={report} lead={lead} section={tab} />}
        </>
      )}

      {tab === 'benchmark' && (
        <>
          <Card title="Competitor Benchmarking">
            <form onSubmit={runBm} className="grid gap-3 md:grid-cols-2">
              <Input label="Your prospect's website" required value={bm.target_url} onChange={(e) => setBm({ ...bm, target_url: e.target.value })} />
              <Textarea label="Competitor URLs (comma or new line)" rows={2} value={bm.competitors} onChange={(e) => setBm({ ...bm, competitors: e.target.value })} />
              <div className="flex flex-wrap items-end gap-3 md:col-span-2">
                <Toggle label="Find competitors automatically (same type & city)" checked={bm.auto_find} onChange={(v) => setBm({ ...bm, auto_find: v })} />
                {bm.auto_find && <><Input label="Business type" value={bm.category} onChange={(e) => setBm({ ...bm, category: e.target.value })} />
                  <Input label="City" value={bm.city} onChange={(e) => setBm({ ...bm, city: e.target.value })} /></>}
                <Button loading={busy}>Compare</Button>
              </div>
            </form>
            {status && <p className="mt-3 text-sm text-[#6D5DF6]">{status}</p>}
          </Card>
          {bmRes && <Benchmark r={bmRes} />}
          {benchmarks.length > 0 && (
            <Card title="Previous benchmarks">
              <Table rows={benchmarks} columns={[{ label: 'When', render: (b) => fmtDate(b.created_at) }, { label: 'Target', key: 'target_url' },
                { label: 'Competitors', render: (b) => (b.competitor_urls || []).length }, { label: '', render: (b) => <Button variant="ghost" onClick={() => setBmRes(b.result || b)}>View</Button> }]} />
            </Card>
          )}
        </>
      )}

      {tab === 'history' && (
        <Card title="Audit history">
          <Table rows={history} empty="No audits yet" columns={[{ label: 'When', render: (a) => fmtDate(a.created_at) },
            { label: 'URL', render: (a) => <span className="break-all">{a.url}</span> }, { label: 'Overall', key: 'overall_score' },
            { label: 'Speed', key: 'speed_score' }, { label: 'Security', key: 'security_score' }, { label: 'Mobile', key: 'mobile_score' },
            { label: 'SEO', key: 'seo_score' }, { label: 'Trust', key: 'trust_score' }, { label: 'Leaks', key: 'leak_count' },
            { label: '', render: (a) => <Button variant="ghost" onClick={() => open(a)}>Open</Button> }]} />
        </Card>
      )}
    </div>
  );
}

function Report({ r, lead, section }) {
  const sevColor = { high: 'red', medium: 'amber', low: 'gray' };
  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-around gap-6">
          <ScoreRing score={r.overall_score} label="Overall" size={110} />
          <ScoreRing score={r.speed?.score} label="Speed" />
          <ScoreRing score={r.security?.score} label="Security" />
          <ScoreRing score={r.mobile?.score} label="Mobile" />
          <ScoreRing score={r.seo?.score} label="SEO / indexing" />
          <ScoreRing score={r.trust?.score} label="Trust & conversion" />
        </div>
        <p className="mt-4 text-center text-xs text-slate-400 break-all">{r.final_url || r.url}</p>
        {r.opportunities?.length > 0 && (
          <div className="mt-5 rounded-xl bg-violet-50 p-4 dark:bg-violet-500/10">
            <p className="mb-2 text-sm font-bold text-violet-800 dark:text-violet-200">Sales opportunities to pitch</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-violet-900 dark:text-violet-100">{r.opportunities.map((o, _i) => <li key={_i}>{txt(o)}</li>)}</ul>
            {lead && <Link href={`/copywriter?business_id=${lead.id}`} className="mt-3 inline-block text-sm font-bold text-[#6D5DF6]">Write an email from these findings →</Link>}
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {section === 'speed' && <Card title="Trust & Conversion Leak Detector" actions={<span className="text-xs text-slate-400">{r.trust?.leak_count} found · {r.trust?.high_severity} high</span>}>
          {!r.trust?.leaks?.length ? <Empty title="No leaks found" /> : (
            <div className="space-y-3">
              {r.trust.leaks.map((l, _i) => (
                <div key={_i} className="rounded-lg border border-slate-100 p-3 dark:border-white/[0.05]">
                  <p className="text-sm font-bold text-slate-900 dark:text-white"><Badge color={sevColor[l.severity]}>{l.severity}</Badge> <Badge>{l.category}</Badge> {l.title}</p>
                  <p className="mt-1 text-xs text-slate-600 dark:text-[#C8C4E8]">{l.impact}</p>
                  <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-300">Fix: {l.fix}</p>
                </div>
              ))}
            </div>
          )}
        </Card>}

        {section === 'speed' && <Card title="Speed & Security Audit · speed" actions={<span className="text-xs text-slate-400">{r.speed?.load_ms} ms load · {r.speed?.ttfb_ms} ms TTFB</span>}>
          <KV items={{ 'HTML size': `${r.speed?.html_kb} KB`, Compression: r.speed?.compression || 'none', Caching: r.speed?.caching ? 'yes' : 'no', Redirects: r.speed?.redirects,
            Scripts: r.speed?.resources?.scripts, Stylesheets: r.speed?.resources?.stylesheets, Images: r.speed?.resources?.images, 'Lazy images': r.speed?.resources?.lazy_images,
            ...(r.speed?.pagespeed ? { 'PageSpeed (mobile)': r.speed.pagespeed.performance } : {}) }} />
          <Tips tips={r.speed?.tips} />
        </Card>}

        {section === 'speed' && <Card title="Speed & Security Audit · security">
          <KV items={{ HTTPS: r.security?.https ? 'yes' : 'no', 'HTTP → HTTPS redirect': r.security?.http_redirects_to_https ? 'yes' : 'no',
            'SSL valid': r.security?.ssl?.valid ? 'yes' : 'no', Issuer: r.security?.ssl?.issuer, 'Expires in': r.security?.ssl?.days_left != null ? `${r.security.ssl.days_left} days` : '-',
            Protocol: r.security?.ssl?.protocol, 'Mixed content': r.security?.mixed_content_links }} />
          <p className="mt-3 text-xs font-bold text-slate-500">Security headers</p>
          <div className="mt-1 flex flex-wrap gap-1">
            {(r.security?.headers?.present || []).map((h, _i) => <Badge key={_i} color="green">{txt(h?.header ?? h)}</Badge>)}
            {(r.security?.headers?.missing || []).map((h, _i) => <Badge key={_i} color="red">{txt(h?.header ?? h)}</Badge>)}
          </div>
          <Tips tips={[...(r.security?.tips || []), ...(r.security?.headers?.recommendations || [])]} />
        </Card>}

        {section === 'tech' && <Card title="Tech Stack Detection">
          {!r.tech_stack?.length ? <Empty title="Nothing detected" /> : (
            <div className="space-y-2">
              {r.tech_stack.map((t, _i) => (
                <div key={_i} className="flex items-center justify-between rounded-lg border border-slate-100 p-2 text-sm dark:border-white/[0.05]">
                  <span><b className="text-slate-900 dark:text-white">{t.name}</b> {t.version && <span className="text-xs">v{t.version}</span>} <span className="text-xs text-slate-400">{t.category}</span></span>
                  {t.outdated ? <Badge color="red">outdated</Badge> : t.version ? <Badge color="green">current</Badge> : null}
                </div>
              ))}
              {r.tech_stack.filter((t) => t.note).map((t, _i) => <p key={_i} className="text-xs text-red-600">{t.note}</p>)}
            </div>
          )}
        </Card>}

        {section === 'mobile' && <Card title="Mobile Friendliness Score">
          <Checks checks={r.mobile?.checks} />
          <Tips tips={r.mobile?.tips} />
        </Card>}

        {section === 'mobile' && <Card title="SEO & search indexing checks (responsiveness + indexing)" actions={<Badge color={r.seo?.indexable ? 'green' : 'red'}>{r.seo?.indexable ? 'indexable' : 'hidden from Google'}</Badge>}>
          <Checks checks={r.seo?.checks} />
        </Card>}
      </div>
    </div>
  );
}

function Benchmark({ r }) {
  return (
    <Card title="Benchmark results">
      <Table rows={r.ranking || []} rowKey="url" columns={[{ label: '#', key: 'rank' },
        { label: 'Site', render: (x) => <span className="break-all">{x.is_target ? <b>{x.url} (prospect)</b> : x.url}</span> },
        { label: 'Overall', key: 'overall_score' }, { label: 'Speed', key: 'speed' }, { label: 'Security', key: 'security' },
        { label: 'Mobile', key: 'mobile' }, { label: 'SEO', key: 'seo' }, { label: 'Trust', key: 'trust' }, { label: 'Load', render: (x) => `${x.load_ms} ms` }]} />
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-[#C8C4E8]">{(r.insights || []).map((i, _i) => <li key={_i}>{txt(i)}</li>)}</ul>
    </Card>
  );
}

function KV({ items }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      {Object.entries(items).flatMap(([k, v]) => [<dt key={`k${k}`} className="text-slate-500">{k}</dt>, <dd key={`v${k}`} className="font-bold text-slate-900 dark:text-white">{txt(v)}</dd>])}
    </dl>
  );
}
function Checks({ checks = [] }) {
  return (
    <div className="space-y-1.5">
      {checks.map((c, _i) => (
        <div key={_i} className="text-sm">
          <span>{c.passed ? '✅' : '❌'} <span className="text-slate-800 dark:text-white">{c.check}</span>{c.detail ? <span className="text-xs text-slate-400"> · {String(c.detail).slice(0, 70)}</span> : null}</span>
          {!c.passed && c.tip && <p className="pl-6 text-xs text-slate-500">{txt(c.tip)}</p>}
        </div>
      ))}
    </div>
  );
}
function Tips({ tips = [] }) {
  if (!tips?.length) return null;
  return <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600 dark:text-[#C8C4E8]">{[...new Set(tips.map(txt))].map((t, _i) => <li key={_i}>{t}</li>)}</ul>;
}

export default function AdvancedAuditsPage() { return <Suspense fallback={null}><Audits /></Suspense>; }