'use client';
// Module 2 - Custom Business Finder: Search by Type & City, Proprietary Web Scraper (httpx + Playwright fallback),
// Data Parser & Extraction, Find Websites Automatically. Long searches run as Celery background jobs.
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, fmtDate, runJob } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, PageHeader, Select, Table, Tabs, Textarea, Toggle } from '../components/ui';

export default function FinderPage() {
  const toast = useToast();
  const [tab, setTab] = useState('search');
  const [types, setTypes] = useState({});
  const [lists, setLists] = useState([]);
  const [q, setQ] = useState({ business_type: 'dentist', city: '', country: '', radius_meters: 8000, max_results: 30, auto_find_websites: true, scrape_contacts: true });
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [sel, setSel] = useState({});
  const [listId, setListId] = useState('');
  const [scrape, setScrape] = useState({ url: '', max_pages: 10 });
  const [scrapeRes, setScrapeRes] = useState(null);
  const [parse, setParse] = useState({ url: '', html: '', text: '' });
  const [parseRes, setParseRes] = useState(null);
  const [history, setHistory] = useState([]);
  const [disc, setDisc] = useState('');
  const [discRes, setDiscRes] = useState(null);

  useEffect(() => {
    api('/finder/business-types').then(setTypes).catch(() => {});
    api('/leads/lists').then((d) => setLists(d.lists || [])).catch(() => {});
    api('/finder/history').then((d) => setHistory(d.jobs || [])).catch(() => {});
  }, []);

  async function search(e) {
    e.preventDefault();
    setBusy(true); setRes(null); setSel({});
    try {
      const r = await runJob('finder_search', { ...q, radius_meters: Number(q.radius_meters), max_results: Number(q.max_results) },
        { onStatus: (j) => setStatus(j.status === 'running' ? `Searching${q.auto_find_websites ? ', finding websites' : ''}${q.scrape_contacts ? ' and scraping contacts' : ''}... (${j.runner || 'queued'})` : j.status) });
      setRes(r);
      const s = {}; (r.results || []).forEach((b, i) => { if (!b.already_saved && !b.duplicates?.length) s[i] = true; }); setSel(s);
      toast(`Found ${r.result_count} businesses`, 'success');
      api('/finder/history').then((d) => setHistory(d.jobs || [])).catch(() => {});
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); setStatus(''); }
  }

  async function save() {
    const chosen = (res?.results || []).filter((_, i) => sel[i]);
    if (!chosen.length) return toast('Select at least one business', 'warning');
    try {
      const r = await api('/finder/save', { method: 'POST', body: { businesses: chosen, list_id: listId || undefined, skip_duplicates: true } });
      toast(r.message || `Saved ${r.saved}`, 'success');
      setRes({ ...res, results: res.results.map((b, i) => (sel[i] ? { ...b, already_saved: true } : b)) }); setSel({});
    } catch (e) { toast(e.message, 'error'); }
  }

  async function doScrape(e) {
    e.preventDefault(); setBusy(true); setScrapeRes(null);
    try { setScrapeRes(await runJob('scrape', { url: scrape.url, max_pages: Number(scrape.max_pages) }, { onStatus: (j) => setStatus(`Crawling (${j.status})...`) })); }
    catch (err) { toast(err.message, 'error'); } finally { setBusy(false); setStatus(''); }
  }
  async function doParse(e) {
    e.preventDefault(); setBusy(true);
    try { setParseRes(await api('/finder/parse', { method: 'POST', body: parse })); } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); }
  }

  async function doDiscover(e) {
    e.preventDefault(); setBusy(true); setDiscRes(null);
    try {
      const businesses = disc.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => { const [business_name, city] = l.split(',').map((x) => x.trim()); return { business_name, city }; });
      setDiscRes(await api('/finder/discover', { method: 'POST', body: { businesses } }));
    } catch (err) { toast(err.message, 'error'); } finally { setBusy(false); }
  }

  const rows = (res?.results || []).map((b, i) => ({ ...b, _i: i }));
  const allTypes = Object.entries(types).flatMap(([g, arr]) => arr.map((t) => ({ value: t, label: `${t} (${g})` })));

  return (
    <div className="space-y-6">
      <PageHeader module="[2] Custom Business Finder" title="Custom Business Finder"
        subtitle="OpenStreetMap search by type & city, automatic website discovery and our own crawler for emails, phones and social links." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'search', label: 'Search by Type & City' }, { id: 'scrape', label: 'Proprietary Web Scraper' },
        { id: 'parse', label: 'Data Parser & Extraction' }, { id: 'websites', label: 'Find Websites Automatically' }, { id: 'history', label: 'History' }]} />

      {tab === 'search' && (
        <>
          <Card>
            <form onSubmit={search} className="grid gap-3 md:grid-cols-6 md:items-end">
              <div className="md:col-span-2">
                <Input label="Business type" list="btypes" required value={q.business_type} onChange={(e) => setQ({ ...q, business_type: e.target.value })} />
                <datalist id="btypes">{allTypes.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}</datalist>
              </div>
              <Input label="City" required value={q.city} onChange={(e) => setQ({ ...q, city: e.target.value })} placeholder="Lahore" />
              <Input label="Country" value={q.country} onChange={(e) => setQ({ ...q, country: e.target.value })} placeholder="Pakistan" />
              <Select label="Radius" value={q.radius_meters} onChange={(e) => setQ({ ...q, radius_meters: e.target.value })}
                options={[3000, 5000, 8000, 15000, 25000].map((v) => ({ value: v, label: `${v / 1000} km` }))} />
              <Input label="Max results" type="number" min="1" max="200" value={q.max_results} onChange={(e) => setQ({ ...q, max_results: e.target.value })} />
              <div className="flex flex-wrap gap-5 md:col-span-4">
                <Toggle label="Find websites automatically" checked={q.auto_find_websites} onChange={(v) => setQ({ ...q, auto_find_websites: v })} />
                <Toggle label="Scrape contacts from websites" checked={q.scrape_contacts} onChange={(v) => setQ({ ...q, scrape_contacts: v })} />
              </div>
              <Button className="md:col-span-2" loading={busy}>Search</Button>
            </form>
            {status && <p className="mt-3 text-sm text-[#6D5DF6]">{status}</p>}
          </Card>

          {res && (
            <Card title={`${res.result_count} results · ${res.with_website} with website · ${res.with_email} with email`}
              actions={<div className="flex items-center gap-2">
                <select value={listId} onChange={(e) => setListId(e.target.value)} className="rounded-lg border border-slate-200 bg-transparent px-2 py-2 text-xs dark:border-white/10">
                  <option value="" className="text-black">No list</option>{lists.map((l) => <option key={l.id} value={l.id} className="text-black">{l.name}</option>)}
                </select>
                <Button onClick={save}>Save selected ({Object.values(sel).filter(Boolean).length})</Button></div>}>
              {res.query?.resolved_location && <p className="mb-3 text-xs text-slate-400">Location: {res.query.resolved_location}</p>}
              <Table rows={rows} rowKey="_i" empty="No businesses found, try a bigger radius or another type" columns={[
                { label: '', render: (b) => <input type="checkbox" className="accent-[#6D5DF6]" checked={!!sel[b._i]} disabled={b.already_saved} onChange={(e) => setSel({ ...sel, [b._i]: e.target.checked })} /> },
                { label: 'Business', render: (b) => <div><p className="font-bold text-slate-900 dark:text-white">{b.business_name}</p><p className="text-xs">{b.address || b.category || ''}</p></div> },
                { label: 'Website', render: (b) => (b.website ? <a href={b.website} target="_blank" rel="noreferrer" className="text-[#6D5DF6] underline">{b.website.replace(/^https?:\/\//, '').slice(0, 30)}</a> : '-') },
                { label: 'Email', render: (b) => b.email || '-' },
                { label: 'Phone', render: (b) => b.phone || '-' },
                { label: 'Social', render: (b) => [b.facebook && 'FB', b.instagram && 'IG'].filter(Boolean).join(' · ') || '-' },
                { label: 'Status', render: (b) => (b.already_saved ? <Badge color="green">saved</Badge> : b.duplicates?.length ? <Badge color="amber">duplicate</Badge> : <Badge>new</Badge>) },
              ]} />
              <p className="mt-3 text-xs text-slate-400">Saved leads go to the <Link href="/leads" className="text-[#6D5DF6]">Lead Manager</Link>. Duplicates are checked against your workspace before saving.</p>
            </Card>
          )}
        </>
      )}

      {tab === 'scrape' && (
        <Card title="Proprietary web scraper" actions={<span className="text-xs text-slate-400">Static HTML first, headless Playwright for JS-heavy sites</span>}>
          <form onSubmit={doScrape} className="grid gap-3 md:grid-cols-[1fr_140px_auto] md:items-end">
            <Input label="Website URL" required value={scrape.url} onChange={(e) => setScrape({ ...scrape, url: e.target.value })} placeholder="https://business.com" />
            <Input label="Max pages" type="number" value={scrape.max_pages} onChange={(e) => setScrape({ ...scrape, max_pages: e.target.value })} />
            <Button loading={busy}>Crawl</Button>
          </form>
          {status && <p className="mt-3 text-sm text-[#6D5DF6]">{status}</p>}
          {scrapeRes && <ContactResult c={{ ...(scrapeRes.parsed || {}), ...(scrapeRes.contacts || {}) }} pages={scrapeRes.contacts?.pages_crawled} />}
        </Card>
      )}

      {tab === 'parse' && (
        <Card title="Data parser & extraction" actions={<span className="text-xs text-slate-400">Paste raw HTML or text, or give a URL</span>}>
          <form onSubmit={doParse} className="space-y-3">
            <Input label="URL (optional)" value={parse.url} onChange={(e) => setParse({ ...parse, url: e.target.value })} />
            <Textarea label="Raw HTML (optional)" rows={5} value={parse.html} onChange={(e) => setParse({ ...parse, html: e.target.value })} />
            <Textarea label="Plain text (optional)" rows={3} value={parse.text} onChange={(e) => setParse({ ...parse, text: e.target.value })} />
            <Button loading={busy}>Extract</Button>
          </form>
          {parseRes && <ContactResult c={parseRes} />}
        </Card>
      )}

      {tab === 'websites' && (
        <Card title="Find Websites Automatically" actions={<span className="text-xs text-slate-400">Also runs automatically during a search when the toggle is on</span>}>
          <form onSubmit={doDiscover} className="space-y-3">
            <Textarea label="One business per line: name, city" rows={6} required value={disc} onChange={(e) => setDisc(e.target.value)} placeholder={'Shaukat Khanum Hospital, Lahore\nBlue Cafe, Dubai'} />
            <Button loading={busy}>Find websites</Button>
          </form>
          {discRes && (
            <div className="mt-5"><p className="mb-2 text-sm"><b>{discRes.found_count}</b> of {discRes.results.length} found</p>
              <Table rows={discRes.results.map((r, i) => ({ ...r, _i: i }))} rowKey="_i" columns={[{ label: 'Business', key: 'business_name' }, { label: 'City', key: 'city' },
                { label: 'Website', render: (r) => (r.website ? <a href={r.website} target="_blank" rel="noreferrer" className="text-[#6D5DF6] underline">{r.website}</a> : <Badge color="amber">not found</Badge>) }]} />
              {discRes.results.some((r) => r.website) && <Button className="mt-3" onClick={async () => {
                try { const r = await api('/finder/save', { method: 'POST', body: { businesses: discRes.results.filter((x) => x.website), skip_duplicates: true } }); toast(r.message || 'Saved', 'success'); } catch (er) { toast(er.message, 'error'); }
              }}>Save found businesses as leads</Button>}
            </div>
          )}
        </Card>
      )}

      {tab === 'history' && (
        <Card title="Search history">
          <Table rows={history} columns={[{ label: 'When', render: (h) => fmtDate(h.created_at) }, { label: 'Kind', key: 'kind' },
            { label: 'Query', render: (h) => h.target_url || `${h.business_type} in ${h.city}${h.country ? ', ' + h.country : ''}` },
            { label: 'Results', key: 'result_count' }]} empty="No searches yet" />
        </Card>
      )}
    </div>
  );
}

function ContactResult({ c, pages }) {
  const socials = { ...(c.socials || {}) };
  ['facebook', 'instagram', 'twitter', 'linkedin', 'youtube', 'tiktok'].forEach((k) => { if (c[k]) socials[k] = c[k]; });
  return (
    <div className="mt-5 grid gap-4 md:grid-cols-3">
      <Box title="Emails" items={c.emails} best={c.best_email} />
      <Box title="Phones" items={[...(c.phones || []), ...(c.whatsapp || []).map((w) => `WhatsApp: ${w}`)]} best={c.best_phone} />
      <Box title="Social profiles" items={Object.entries(socials).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)} />
      {(c.title || c.description) && <div className="md:col-span-3 text-sm text-slate-600 dark:text-[#C8C4E8]"><b>{c.title}</b>{c.description && ` - ${c.description}`}</div>}
      {c.business && Object.keys(c.business).length > 0 && <pre className="md:col-span-3 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs dark:bg-white/[0.03]">{JSON.stringify(c.business, null, 2)}</pre>}
      {pages?.length > 0 && <p className="md:col-span-3 text-xs text-slate-400">Pages crawled: {pages.join(', ')}</p>}
    </div>
  );
}

function Box({ title, items = [], best }) {
  return (
    <div className="rounded-lg border border-slate-100 p-3 dark:border-white/[0.05]">
      <p className="mb-2 text-xs font-bold uppercase text-slate-500">{title}</p>
      {!items?.length ? <p className="text-sm text-slate-400">None found</p> : items.map((i) => (
        <p key={i} className="break-all text-sm text-slate-800 dark:text-white">{i} {best && i === best && <Badge color="green">best</Badge>}</p>))}
    </div>
  );
}
