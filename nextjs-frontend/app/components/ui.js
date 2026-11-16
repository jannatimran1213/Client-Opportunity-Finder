'use client';
// Small shared UI kit in the existing visual style (rounded-xl cards, #6D5DF6 accent, dark mode).

export function PageHeader({ title, subtitle, module, actions }) {
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        {module && <p className="mb-1 text-xs font-bold uppercase tracking-wider text-[#6D5DF6] dark:text-[#A78BFA]">{module}</p>}
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500 dark:text-[#8E8BA3]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = '', title, actions }) {
  return (
    <div className={`rounded-xl border border-slate-200/80 bg-white p-5 dark:border-white/[0.06] dark:bg-white/[0.015] ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between gap-2">
          {title && <h3 className="text-base font-bold text-slate-900 dark:text-white">{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export function Button({ children, variant = 'primary', className = '', loading, ...props }) {
  const styles = {
    primary: 'bg-[#6D5DF6] hover:bg-[#5b4ee4] text-white',
    secondary: 'border border-slate-200 dark:border-white/[0.08] bg-white/60 dark:bg-white/[0.04] text-slate-700 dark:text-[#C8C4E8] hover:text-slate-900 dark:hover:text-white',
    danger: 'bg-red-500/90 hover:bg-red-500 text-white',
    ghost: 'text-slate-500 dark:text-[#8E8BA3] hover:text-slate-900 dark:hover:text-white',
    success: 'bg-emerald-500 hover:bg-emerald-600 text-white',
  };
  return (
    <button {...props} disabled={props.disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}>
      {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}

const fieldCls = 'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-[#6D5DF6] dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-white';

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-[#C8C4E8]">{label}</span>}
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-[#6B6890]">{hint}</span>}
    </label>
  );
}

export function Input({ label, hint, className = '', ...props }) {
  return <Field label={label} hint={hint} className={className}><input {...props} className={fieldCls} /></Field>;
}

export function Textarea({ label, hint, className = '', rows = 4, ...props }) {
  return <Field label={label} hint={hint} className={className}><textarea rows={rows} {...props} className={fieldCls} /></Field>;
}

export function Select({ label, hint, options = [], className = '', ...props }) {
  return (
    <Field label={label} hint={hint} className={className}>
      <select {...props} className={fieldCls}>
        {options.map((o) => (typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>))}
      </select>
    </Field>
  );
}

export function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-[#C8C4E8]">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-[#6D5DF6]" />
      {label}
    </label>
  );
}

const badgeColors = {
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  blue: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  purple: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  gray: 'bg-slate-100 text-slate-600 dark:bg-white/[0.06] dark:text-[#C8C4E8]',
};

export function Badge({ children, color = 'gray' }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ${badgeColors[color] || badgeColors.gray}`}>{children}</span>;
}

export function statusColor(s) {
  return ({ valid: 'green', reachable: 'green', done: 'green', won: 'green', sent: 'green', completed: 'green', delivered: 'green', read: 'green', opened: 'blue', clicked: 'purple',
    invalid: 'red', unreachable: 'red', failed: 'red', lost: 'red', overdue: 'red', cancelled: 'red',
    risky: 'amber', unknown: 'amber', simulated: 'amber', today: 'amber', queued: 'blue', meeting: 'purple', contacted: 'blue', replied: 'purple', scheduled: 'blue' })[s] || 'gray';
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl border border-slate-200/80 bg-white/60 p-1 dark:border-white/[0.06] dark:bg-white/[0.02]">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`rounded-lg px-3.5 py-2 text-sm font-bold transition ${active === t.id
            ? 'bg-[#6D5DF6] text-white shadow-sm'
            : 'text-slate-500 hover:text-slate-900 dark:text-[#8E8BA3] dark:hover:text-white'}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ title = 'Nothing here yet', text }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 p-10 text-center dark:border-white/[0.08]">
      <p className="font-bold text-slate-700 dark:text-white">{title}</p>
      {text && <p className="mt-1 text-sm text-slate-500 dark:text-[#8E8BA3]">{text}</p>}
    </div>
  );
}

export function ScoreRing({ score, label, size = 84 }) {
  const s = Math.round(Number(score) || 0);
  const color = s >= 80 ? '#10B981' : s >= 60 ? '#3B82F6' : s >= 40 ? '#F59E0B' : '#EF4444';
  const r = 34, c = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox="0 0 80 80">
        <circle cx="40" cy="40" r={r} stroke="currentColor" className="text-slate-200 dark:text-white/10" strokeWidth="7" fill="none" />
        <circle cx="40" cy="40" r={r} stroke={color} strokeWidth="7" fill="none" strokeDasharray={c} strokeDashoffset={c - (c * s) / 100}
          strokeLinecap="round" transform="rotate(-90 40 40)" />
        <text x="40" y="46" textAnchor="middle" className="fill-slate-900 dark:fill-white" fontSize="18" fontWeight="800">{s}</text>
      </svg>
      {label && <span className="text-xs font-bold text-slate-500 dark:text-[#8E8BA3]">{label}</span>}
    </div>
  );
}

export function Progress({ value, max }) {
  const pct = max ? Math.min(100, Math.round((100 * value) / max)) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/[0.08]">
      <div className={`h-full rounded-full ${pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : 'bg-[#6D5DF6]'}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={`max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#0B0914] ${wide ? 'max-w-3xl' : 'max-w-lg'}`}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-white">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Table({ columns, rows, empty = 'No rows', rowKey = 'id' }) {
  if (!rows?.length) return <Empty title={empty} />;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200/80 dark:border-white/[0.06]">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500 dark:bg-white/[0.03] dark:text-[#8E8BA3]">
          <tr>{columns.map((c) => <th key={c.key || c.label} className="px-4 py-3 font-bold">{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-white/[0.04]">
          {rows.map((r, i) => (
            <tr key={r[rowKey] || i} className="hover:bg-slate-50/60 dark:hover:bg-white/[0.02]">
              {columns.map((c) => <td key={c.key || c.label} className="px-4 py-3 align-top text-slate-700 dark:text-[#C8C4E8]">{c.render ? c.render(r) : r[c.key] ?? '-'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function useCopy() {
  return async (text) => { try { await navigator.clipboard.writeText(text); return true; } catch { return false; } };
}
