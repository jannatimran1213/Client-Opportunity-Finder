'use client';
// Module 8 - Drag-and-Drop Builder: pages list, Industry-Specific Ready-Made Designs (templates gallery),
// Live Subdomain Hosting status, import of an exported page.json.
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, download, fmtDate } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, Empty, Input, Modal, PageHeader, Select, Tabs } from '../components/ui';

export default function BuilderHome() {
  const toast = useToast();
  const router = useRouter();
  const fileRef = useRef(null);
  const [tab, setTab] = useState('pages');
  const [pages, setPages] = useState([]);
  const [base, setBase] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [leads, setLeads] = useState([]);
  const [create, setCreate] = useState(null);
  const [preview, setPreview] = useState(null);

  const load = () => api('/builder/pages').then((d) => { setPages(d.pages || []); setBase(d.sites_base_domain); }).catch((e) => toast(e.message, 'error'));
  useEffect(() => {
    load();
    api('/builder/templates').then((d) => setTemplates(d.templates || [])).catch(() => {});
    api('/leads', { params: { per_page: 500 } }).then((d) => setLeads(d.leads || [])).catch(() => {});
  }, []);

  async function doCreate(e) {
    e.preventDefault();
    try {
      const p = await api('/builder/pages', { method: 'POST', body: { name: create.name, kind: create.kind, template_key: create.template_key || undefined, business_id: create.business_id || undefined } });
      router.push(`/builder/${p.id}`);
    } catch (err) { toast(err.message, 'error'); }
  }
  async function showPreview(t) {
    try {
      const res = await fetch(`/api/v1/builder/templates/${t.key}/preview`, { headers: { Authorization: `Bearer ${localStorage.getItem('access_token') || localStorage.getItem('token')}`, 'X-Workspace-Id': localStorage.getItem('workspace_id') || '' } });
      setPreview({ t, html: await res.text() });
    } catch (e) { toast(e.message, 'error'); }
  }
  async function dup(p) { try { await api(`/builder/pages/${p.id}/duplicate`, { method: 'POST' }); load(); } catch (e) { toast(e.message, 'error'); } }
  async function del(p) { if (!confirm(`Delete "${p.name}"?`)) return; try { await api(`/builder/pages/${p.id}`, { method: 'DELETE' }); load(); } catch (e) { toast(e.message, 'error'); } }
  async function importFile(e) {
    const f = e.target.files?.[0]; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      const p = await api('/builder/pages/import', { method: 'POST', body: data });
      toast('Page imported', 'success'); router.push(`/builder/${p.id}`);
    } catch (err) { toast(`Import failed: ${err.message}`, 'error'); } finally { e.target.value = ''; }
  }

  const pagesT = templates.filter((t) => t.kind === 'page');
  const emailsT = templates.filter((t) => t.kind === 'email');

  return (
    <div className="space-y-6">
      <PageHeader module="[8] Drag-and-Drop Builder" title="Drag-and-Drop Builder"
        subtitle="Build a mock-up site or email for a prospect without code, host it on its own subdomain for review, then export clean HTML/CSS/JS."
        actions={<><input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={importFile} />
          <Button variant="secondary" onClick={() => fileRef.current?.click()}>Import page.json</Button>
          <Button onClick={() => setCreate({ name: 'New page', kind: 'page', template_key: '', business_id: '' })}>New blank page</Button></>} />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'pages', label: `My pages · Visual Editor (${pages.length})` }, { id: 'templates', label: 'Industry-Specific Ready-Made Designs' }]} />

      {tab === 'pages' && (!pages.length ? <Empty title="No pages yet" text="Start from a ready-made industry design" /> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {pages.map((p) => (
            <Card key={p.id}>
              <div className="flex items-start justify-between gap-2">
                <div><p className="font-bold text-slate-900 dark:text-white">{p.name}</p><p className="text-xs text-slate-500">{p.kind} · {p.block_count} blocks · edited {fmtDate(p.updated_at)}</p></div>
                {p.published ? <Badge color="green">live</Badge> : <Badge>draft</Badge>}
              </div>
              {p.published && p.public_url && <a href={p.public_url} target="_blank" rel="noreferrer" className="mt-2 block break-all text-xs font-bold text-[#6D5DF6]">{p.public_url}</a>}
              {p.published && <p className="text-xs text-slate-400">{p.view_count} views</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={() => router.push(`/builder/${p.id}`)}>Edit</Button>
                <Button variant="secondary" onClick={() => download(`/builder/pages/${p.id}/export`, `${p.subdomain || p.name.replace(/\W+/g, '-').toLowerCase()}.zip`)}>Export code</Button>
                <Button variant="ghost" onClick={() => dup(p)}>Duplicate</Button>
                <Button variant="ghost" onClick={() => del(p)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      ))}

      {tab === 'templates' && (
        <div className="space-y-6">
          {[['Website designs by industry', pagesT], ['Email templates', emailsT]].map(([title, list]) => (
            <div key={title}>
              <h3 className="mb-3 text-sm font-bold uppercase text-slate-500">{title}</h3>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {list.map((t) => (
                  <Card key={t.key} className="overflow-hidden !p-0">
                    {t.preview_image ? <img src={t.preview_image} alt="" className="h-36 w-full object-cover" /> : <div className="h-36" style={{ background: t.theme?.primary }} />}
                    <div className="p-4">
                      <p className="font-bold text-slate-900 dark:text-white">{t.name}</p>
                      <p className="text-xs text-slate-500">{t.industry} · {t.block_count} blocks <span className="inline-block h-3 w-3 rounded-full align-middle" style={{ background: t.theme?.primary }} /></p>
                      <div className="mt-3 flex gap-2">
                        <Button onClick={() => setCreate({ name: t.name, kind: t.kind, template_key: t.key, business_id: '' })}>Use</Button>
                        <Button variant="secondary" onClick={() => showPreview(t)}>Preview</Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={!!create} onClose={() => setCreate(null)} title={create?.template_key ? `New page from "${create.name}"` : 'New page'}>
        {create && (
          <form onSubmit={doCreate} className="space-y-3">
            <Input label="Page name" required value={create.name} onChange={(e) => setCreate({ ...create, name: e.target.value })} />
            {!create.template_key && <Select label="Kind" value={create.kind} onChange={(e) => setCreate({ ...create, kind: e.target.value })} options={[{ value: 'page', label: 'Website page' }, { value: 'email', label: 'Email' }]} />}
            <Select label="Personalise for a lead (fills name, phone, email, address)" value={create.business_id} onChange={(e) => setCreate({ ...create, business_id: e.target.value })}
              options={[{ value: '', label: 'No lead' }, ...leads.map((l) => ({ value: l.id, label: l.business_name }))]} />
            <Button>Create & open editor</Button>
          </form>
        )}
      </Modal>

      <Modal open={!!preview} onClose={() => setPreview(null)} title={preview?.t?.name || ''} wide>
        {preview && <iframe title="preview" srcDoc={preview.html} sandbox="allow-scripts allow-popups" className="h-[70vh] w-full rounded-lg border border-slate-200 bg-white" />}
      </Modal>
      {base === null && pages.some((p) => p.published) && <p className="text-xs text-slate-400">Pages are served at /sites/&lt;name&gt; on the backend. Set SITES_BASE_DOMAIN (and wildcard DNS) to serve them at &lt;name&gt;.yourdomain.com.</p>}
    </div>
  );
}
