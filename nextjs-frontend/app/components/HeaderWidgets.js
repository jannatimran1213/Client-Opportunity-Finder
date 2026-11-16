'use client';
// Module 1 (workspace switcher) + Module 7 (notifications bell) shown in the app header.
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { api, fmtDate, getWorkspaceId, setWorkspaceId } from '../lib/client';

export function WorkspaceSwitcher() {
  const [list, setList] = useState([]);
  const [current, setCurrent] = useState('');

  useEffect(() => {
    api('/workspaces').then((d) => {
      const ws = d.workspaces || [];
      setList(ws);
      let id = getWorkspaceId();
      if (!id || !ws.find((w) => w.id === id)) {
        id = ws[0]?.id || '';
        if (id) setWorkspaceId(id);
      }
      setCurrent(id);
    }).catch(() => {});
  }, []);

  if (!list.length) return null;
  return (
    <select value={current} title="Active workspace"
      onChange={(e) => { setWorkspaceId(e.target.value); setCurrent(e.target.value); window.location.reload(); }}
      className="hidden max-w-[200px] rounded-xl border border-slate-200/80 bg-white/60 px-3 py-2 text-xs font-bold text-slate-700 dark:border-white/[0.06] dark:bg-white/[0.04] dark:text-[#C8C4E8] md:block">
      {list.map((w) => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}
    </select>
  );
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ unread: 0, notifications: [] });
  const ref = useRef(null);

  const load = useCallback(() => {
    if (!getWorkspaceId()) return;
    api('/notifications').then(setData).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    window.addEventListener('workspace-changed', load);
    return () => { clearInterval(t); document.removeEventListener('mousedown', close); window.removeEventListener('workspace-changed', load); };
  }, [load]);

  async function readAll() {
    await api('/notifications/read-all', { method: 'POST' }).catch(() => {});
    load();
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => { setOpen(!open); if (!open) load(); }}
        className="relative rounded-xl border border-slate-200/80 bg-white/60 p-2 text-slate-600 dark:border-white/[0.06] dark:bg-white/[0.04] dark:text-[#C8C4E8]" title="Notifications">
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
        {data.unread > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">{data.unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-xl dark:border-white/10 dark:bg-[#0B0914]">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-sm font-bold text-slate-900 dark:text-white">Notifications</span>
            <button onClick={readAll} className="text-xs font-bold text-[#6D5DF6]">Mark all read</button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {data.notifications.length === 0 && <p className="p-4 text-center text-sm text-slate-500">You're all caught up</p>}
            {data.notifications.map((n) => (
              <Link key={n.id} href={n.link || '/meetings'} onClick={() => setOpen(false)}
                className={`block rounded-lg px-3 py-2 hover:bg-slate-50 dark:hover:bg-white/[0.03] ${n.read ? 'opacity-60' : ''}`}>
                <p className="text-sm font-bold text-slate-900 dark:text-white">{n.title}</p>
                {n.body && <p className="text-xs text-slate-500 dark:text-[#8E8BA3]">{n.body}</p>}
                <p className="mt-0.5 text-[10px] text-slate-400">{fmtDate(n.created_at)}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
