'use client';
// Module 8 - Visual Editor: HTML5 drag-and-drop canvas (drag blocks from the palette, drag to reorder),
// per-block property editor, theme editor, live preview (desktop / mobile), publish to a subdomain
// (Live Subdomain Hosting) and Export Project (Code) as a zip of index.html + styles.css + script.js.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, apiText, download } from '../../lib/client';
import { useToast } from '../../components/ToastProvider';
import { Badge, Button, Input, Modal } from '../../components/ui';

const FONTS = ['Inter', 'Poppins', 'Roboto', 'Montserrat', 'Lato', 'Playfair Display', 'Merriweather', 'Open Sans'];
const LONG = ['body', 'text', 'quote', 'subheading', 'description'];
const uid = () => Math.random().toString(36).slice(2, 12);

export default function Editor() {
  const { id } = useParams();
  const router = useRouter();
  const toast = useToast();
  const [page, setPage] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [theme, setTheme] = useState({});
  const [palette, setPalette] = useState([]);
  const [sel, setSel] = useState(null);
  const [html, setHtml] = useState('');
  const [device, setDevice] = useState('desktop');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dropAt, setDropAt] = useState(null);
  const [panel, setPanel] = useState('block');
  const [publish, setPublish] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    Promise.all([api(`/builder/pages/${id}`), api('/builder/blocks')]).then(([p, b]) => {
      setPage(p); setBlocks((p.blocks || []).map((x) => ({ ...x, id: x.id || uid() }))); setTheme(p.theme || {}); setPalette(b.blocks || []);
    }).catch((e) => toast(e.message, 'error'));
  }, [id]);

  const render = useCallback((bl, th) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      apiText('/builder/render', { blocks: bl, theme: th, kind: page?.kind || 'page', name: page?.name }).then(setHtml).catch(() => {});
    }, 350);
  }, [page]);
  useEffect(() => { if (page) render(blocks, theme); }, [blocks, theme, page, render]);

  // warn on leaving with unsaved changes
  useEffect(() => {
    const h = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', h); return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);

  const change = (next) => { setBlocks(next); setDirty(true); };
  function insertBlock(type, at) {
    const def = palette.find((p) => p.type === type); if (!def) return;
    const b = { id: uid(), type, props: JSON.parse(JSON.stringify(def.default_props || {})) };
    const next = [...blocks]; next.splice(at ?? next.length, 0, b); change(next); setSel(b.id); setPanel('block');
  }
  function moveBlock(from, to) {
    if (from === to || from + 1 === to) return;
    const next = [...blocks]; const [b] = next.splice(from, 1); next.splice(to > from ? to - 1 : to, 0, b); change(next);
  }
  function onDrop(e, at) {
    e.preventDefault(); setDropAt(null);
    const type = e.dataTransfer.getData('block-type'); const from = e.dataTransfer.getData('block-index');
    if (type) insertBlock(type, at); else if (from !== '') moveBlock(Number(from), at);
  }
  const updateProps = (bid, props) => change(blocks.map((b) => (b.id === bid ? { ...b, props } : b)));
  const remove = (bid) => { change(blocks.filter((b) => b.id !== bid)); if (sel === bid) setSel(null); };
  const duplicate = (i) => { const next = [...blocks]; next.splice(i + 1, 0, { ...JSON.parse(JSON.stringify(blocks[i])), id: uid() }); change(next); };

  async function save() {
    setSaving(true);
    try { const p = await api(`/builder/pages/${id}`, { method: 'PUT', body: { name: page.name, blocks, theme } }); setPage({ ...page, ...p }); setDirty(false); toast('Saved', 'success'); return true; }
    catch (e) { toast(e.message, 'error'); return false; } finally { setSaving(false); }
  }
  async function checkSub(name) {
    setPublish((p) => ({ ...p, name, check: null }));
    if (!name) return;
    try { const r = await api('/builder/subdomain-available', { params: { name } }); setPublish((p) => ({ ...p, check: r })); } catch (e) { setPublish((p) => ({ ...p, check: { available: false, error: e.message } })); }
  }
  async function doPublish() {
    if (dirty && !(await save())) return;
    try { const r = await api(`/builder/pages/${id}/publish`, { method: 'POST', body: { subdomain: publish.name } }); setPage({ ...page, ...r }); setPublish(null); toast('Live!', 'success'); }
    catch (e) { toast(e.message, 'error'); }
  }
  async function unpublish() {
    try { const r = await api(`/builder/pages/${id}/unpublish`, { method: 'POST' }); setPage({ ...page, ...r }); toast('Taken offline', 'info'); } catch (e) { toast(e.message, 'error'); }
  }
  async function exportZip() {
    if (dirty && !(await save())) return;
    download(`/builder/pages/${id}/export`, `${page.subdomain || page.name.replace(/\W+/g, '-').toLowerCase()}.zip`).catch((e) => toast(e.message, 'error'));
  }

  if (!page) return <div className="p-10 text-center text-slate-500">Loading editor...</div>;
  const selected = blocks.find((b) => b.id === sel);
  const label = (t) => palette.find((p) => p.type === t)?.label || t;

  return (
    <div className="-m-2 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => (!dirty || confirm('Leave without saving?')) && router.push('/builder')}>← Pages</Button>
          <input value={page.name} onChange={(e) => { setPage({ ...page, name: e.target.value }); setDirty(true); }}
            className="rounded-lg border border-transparent bg-transparent px-2 py-1 text-lg font-bold text-slate-900 hover:border-slate-200 dark:text-white dark:hover:border-white/10" />
          <Badge>{page.kind}</Badge>{page.published ? <Badge color="green">live</Badge> : <Badge>draft</Badge>}{dirty && <Badge color="amber">unsaved</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 dark:border-white/10">
            {['desktop', 'mobile'].map((d) => <button key={d} onClick={() => setDevice(d)} className={`rounded-md px-3 py-1 text-xs font-bold ${device === d ? 'bg-[#6D5DF6] text-white' : 'text-slate-500'}`}>{d}</button>)}
          </div>
          <Button variant="secondary" onClick={exportZip}>Export code</Button>
          {page.published
            ? <><a href={page.public_url} target="_blank" rel="noreferrer"><Button variant="success">Open live site</Button></a><Button variant="ghost" onClick={unpublish}>Unpublish</Button></>
            : page.kind === 'page' && <Button variant="secondary" onClick={() => checkSub(page.subdomain || page.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40))}>Publish</Button>}
          <Button onClick={save} loading={saving}>Save</Button>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[200px_300px_1fr]" style={{ minHeight: 'calc(100vh - 190px)' }}>
        {/* Palette */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/[0.06] dark:bg-white/[0.015]">
          <p className="mb-2 text-xs font-bold uppercase text-slate-500">Blocks · drag onto the page</p>
          <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-1">
            {palette.map((p) => (
              <div key={p.type} draggable onDragStart={(e) => { e.dataTransfer.setData('block-type', p.type); e.dataTransfer.effectAllowed = 'copy'; }}
                onDoubleClick={() => insertBlock(p.type)} title="Drag onto the page, or double-click to add at the end"
                className="cursor-grab rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:border-[#6D5DF6] active:cursor-grabbing dark:border-white/10 dark:text-[#C8C4E8]">
                ⠿ {p.label}
              </div>
            ))}
          </div>
        </div>

        {/* Canvas (structure) + inspector */}
        <div className="flex flex-col gap-3">
          <div className="rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/[0.06] dark:bg-white/[0.015]">
            <p className="mb-2 text-xs font-bold uppercase text-slate-500">Page structure</p>
            <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => onDrop(e, blocks.length)} className="min-h-[60px]">
              {blocks.map((b, i) => (
                <div key={b.id}>
                  <div onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDropAt(i); }} onDragLeave={() => setDropAt(null)} onDrop={(e) => { e.stopPropagation(); onDrop(e, i); }}
                    className={`h-2 rounded transition-all ${dropAt === i ? 'h-6 bg-[#6D5DF6]/30' : ''}`} />
                  <div draggable onDragStart={(e) => { e.dataTransfer.setData('block-index', String(i)); e.dataTransfer.effectAllowed = 'move'; }}
                    onClick={() => { setSel(b.id); setPanel('block'); }}
                    className={`group flex cursor-grab items-center justify-between rounded-lg border px-2 py-2 text-sm ${sel === b.id ? 'border-[#6D5DF6] bg-violet-50 dark:bg-violet-500/10' : 'border-slate-200 dark:border-white/10'}`}>
                    <span className="truncate font-bold text-slate-800 dark:text-white">⠿ {label(b.type)} <span className="font-normal text-slate-400">{(b.props?.heading || b.props?.text || '').toString().replace(/<[^>]+>/g, '').slice(0, 22)}</span></span>
                    <span className="flex shrink-0 gap-1 text-xs opacity-60 group-hover:opacity-100">
                      <button title="Up" disabled={i === 0} onClick={(e) => { e.stopPropagation(); moveBlock(i, i - 1); }}>↑</button>
                      <button title="Down" disabled={i === blocks.length - 1} onClick={(e) => { e.stopPropagation(); moveBlock(i, i + 2); }}>↓</button>
                      <button title="Duplicate" onClick={(e) => { e.stopPropagation(); duplicate(i); }}>⧉</button>
                      <button title="Delete" className="text-red-500" onClick={(e) => { e.stopPropagation(); remove(b.id); }}>✕</button>
                    </span>
                  </div>
                </div>
              ))}
              <div onDragOver={(e) => { e.preventDefault(); setDropAt(blocks.length); }} onDragLeave={() => setDropAt(null)}
                className={`mt-2 rounded-lg border-2 border-dashed p-3 text-center text-xs text-slate-400 ${dropAt === blocks.length ? 'border-[#6D5DF6] text-[#6D5DF6]' : 'border-slate-200 dark:border-white/10'}`}>Drop a block here</div>
            </div>
          </div>

          <div className="flex-1 rounded-xl border border-slate-200/80 bg-white p-3 dark:border-white/[0.06] dark:bg-white/[0.015]">
            <div className="mb-3 flex gap-1">
              {['block', 'theme'].map((t) => <button key={t} onClick={() => setPanel(t)} className={`rounded-md px-3 py-1 text-xs font-bold ${panel === t ? 'bg-[#6D5DF6] text-white' : 'text-slate-500'}`}>{t === 'block' ? 'Block settings' : 'Theme'}</button>)}
            </div>
            {panel === 'theme' ? (
              <div className="space-y-3">
                {['primary', 'background', 'text', 'muted', 'surface'].map((k) => (
                  <label key={k} className="flex items-center justify-between text-sm capitalize text-slate-700 dark:text-[#C8C4E8]">{k}
                    <input type="color" value={theme[k] || '#ffffff'} onChange={(e) => { setTheme({ ...theme, [k]: e.target.value }); setDirty(true); }} /></label>
                ))}
                <label className="block text-sm text-slate-700 dark:text-[#C8C4E8]">Font
                  <select value={theme.font || 'Inter'} onChange={(e) => { setTheme({ ...theme, font: e.target.value }); setDirty(true); }} className="mt-1 w-full rounded-lg border border-slate-200 bg-transparent p-2 dark:border-white/10">
                    {FONTS.map((f) => <option key={f} className="text-black">{f}</option>)}</select></label>
                <label className="block text-sm text-slate-700 dark:text-[#C8C4E8]">Corner radius
                  <input type="range" min="0" max="28" value={parseInt(theme.radius || '14', 10)} onChange={(e) => { setTheme({ ...theme, radius: `${e.target.value}px` }); setDirty(true); }} className="w-full accent-[#6D5DF6]" /></label>
              </div>
            ) : selected ? (
              <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
                <p className="text-sm font-bold text-slate-900 dark:text-white">{label(selected.type)}</p>
                <PropsEditor value={selected.props || {}} onChange={(p) => updateProps(selected.id, p)} />
              </div>
            ) : <p className="text-sm text-slate-400">Click a block to edit its text, images and links.</p>}
          </div>
        </div>

        {/* Live preview */}
        <div className="flex justify-center overflow-hidden rounded-xl border border-slate-200/80 bg-slate-100 p-3 dark:border-white/[0.06] dark:bg-black/30">
          <iframe title="Live preview" srcDoc={html} sandbox="allow-scripts allow-popups"
            className="h-full min-h-[600px] rounded-lg bg-white shadow-lg transition-all" style={{ width: device === 'mobile' ? 390 : '100%' }} />
        </div>
      </div>

      <Modal open={!!publish} onClose={() => setPublish(null)} title="Publish to a live subdomain">
        {publish && (
          <div className="space-y-3">
            <Input label="Subdomain" value={publish.name} onChange={(e) => checkSub(e.target.value.toLowerCase())} hint="Lowercase letters, numbers and dashes" />
            {publish.check && (publish.check.available
              ? <p className="text-sm text-emerald-600">Available: <b className="break-all">{publish.check.url}</b></p>
              : <p className="text-sm text-red-500">{publish.check.error || publish.check.reason || 'Not available'}</p>)}
            <Button disabled={!publish.check?.available} onClick={doPublish}>Publish now</Button>
            <p className="text-xs text-slate-400">The prospect can open the link and use the contact form; submissions become leads and notifications.</p>
          </div>
        )}
      </Modal>
    </div>
  );
}

function PropsEditor({ value, onChange }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  return (
    <div className="space-y-3">
      {Object.entries(value).map(([k, v]) => <Field key={k} name={k} value={v} onChange={(nv) => set(k, nv)} />)}
    </div>
  );
}

function Field({ name, value, onChange }) {
  const cls = 'mt-1 w-full rounded-lg border border-slate-200 bg-transparent p-2 text-sm text-slate-900 outline-none focus:border-[#6D5DF6] dark:border-white/10 dark:text-white';
  const title = <span className="text-xs font-bold capitalize text-slate-600 dark:text-[#C8C4E8]">{name.replace(/_/g, ' ')}</span>;
  if (typeof value === 'boolean') return <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-[#6D5DF6]" checked={value} onChange={(e) => onChange(e.target.checked)} />{title}</label>;
  if (typeof value === 'number') return <label className="block">{title}<input type="number" className={cls} value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>;
  if (name === 'align') return <label className="block">{title}<select className={cls} value={value} onChange={(e) => onChange(e.target.value)}>{['left', 'center', 'right'].map((a) => <option key={a} className="text-black">{a}</option>)}</select></label>;
  if (Array.isArray(value)) {
    const blank = value.length && typeof value[0] === 'object' ? Object.fromEntries(Object.entries(value[0]).map(([k, v]) => [k, Array.isArray(v) ? [] : typeof v === 'number' ? 0 : ''])) : '';
    return (
      <div>
        {title}
        <div className="mt-1 space-y-2">
          {value.map((item, i) => (
            <div key={i} className="rounded-lg border border-slate-100 p-2 dark:border-white/[0.06]">
              <div className="mb-1 flex justify-between text-[10px] font-bold uppercase text-slate-400">#{i + 1}<button className="text-red-500" onClick={() => onChange(value.filter((_, j) => j !== i))}>remove</button></div>
              {typeof item === 'object' && item !== null
                ? <PropsEditor value={item} onChange={(nv) => onChange(value.map((x, j) => (j === i ? nv : x)))} />
                : <input className={cls} value={item} onChange={(e) => onChange(value.map((x, j) => (j === i ? e.target.value : x)))} />}
            </div>
          ))}
          <button className="text-xs font-bold text-[#6D5DF6]" onClick={() => onChange([...value, JSON.parse(JSON.stringify(blank))])}>+ Add item</button>
        </div>
      </div>
    );
  }
  if (value && typeof value === 'object') return <div>{title}<div className="mt-1 rounded-lg border border-slate-100 p-2 dark:border-white/[0.06]"><PropsEditor value={value} onChange={onChange} /></div></div>;
  const long = LONG.includes(name) || String(value || '').length > 70;
  return (
    <label className="block">{title}
      {long ? <textarea rows={4} className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
        : <input className={cls} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />}
      {(name === 'image' || name === 'src') && value && <img src={value} alt="" className="mt-1 h-16 rounded object-cover" />}
    </label>
  );
}
