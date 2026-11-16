'use client';
// Module 1 - Create an Account: real signup (creates user + personal workspace + Basic trial).
// Supports team invites: /signup?invite=<token> joins the inviting agency's workspace.
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || 'https://ai-client-hunting-backend.onrender.com';

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get('invite') || '';
  const [form, setForm] = useState({ full_name: '', email: params.get('email') || '', password: '', confirm: '', workspace_name: '' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { fetch(`${API}/health`).catch(() => {}); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError('');
    if (form.password.length < 8) return setError('Password must be at least 8 characters');
    if (form.password !== form.confirm) return setError('Passwords do not match');
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: form.full_name, email: form.email, password: form.password,
          workspace_name: form.workspace_name || undefined, invite_token: invite || undefined }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = data.detail;
        throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join(', ') : 'Sign up failed');
      }
      if (data.token) {
        localStorage.setItem('access_token', data.token);
        localStorage.setItem('token', data.token);
        if (data.user?.full_name) localStorage.setItem('user_name', data.user.full_name);
        if (data.workspace_id) localStorage.setItem('workspace_id', data.workspace_id);
        window.dispatchEvent(new Event('storage'));
        router.replace('/dashboard');
      } else {
        setNotice(data.message || 'Account created. Check your email to verify your address, then log in.');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  const input = 'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-[#6D5DF6] dark:border-white/[0.08] dark:bg-white/[0.03] dark:text-white';
  return (
    <main className="mx-auto grid min-h-[calc(100vh-154px)] max-w-7xl items-center gap-10 px-5 py-12 lg:grid-cols-[0.95fr_1.05fr]">
      <div>
        <p className="mb-4 text-xs font-bold uppercase tracking-wider text-[#6D5DF6] dark:text-[#A78BFA]">OrbiScout · [1] Sign Up & SaaS Access · Create an Account</p>
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-slate-900 dark:text-white md:text-5xl">
          {invite ? 'Join your team on OrbiScout' : 'Create your agency workspace'}
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-slate-600 dark:text-[#8E8BA3]">
          Find local businesses, audit their websites, write AI outreach and book meetings, all in one private workspace.
          Every account starts with a 14-day Basic trial.
        </p>
        <ul className="mt-6 space-y-2 text-sm text-slate-600 dark:text-[#C8C4E8]">
          <li>✓ Private multi-tenant workspace: your data is isolated from other agencies</li>
          <li>✓ Invite team members with Owner / Admin / Member / Viewer roles</li>
          <li>✓ Basic, Pro or Enterprise plans, monthly or yearly</li>
        </ul>
      </div>

      <form onSubmit={submit} className="rounded-2xl border border-slate-200/80 bg-white p-8 shadow-sm dark:border-white/[0.06] dark:bg-white/[0.015]">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Sign up</h2>
        {invite && <p className="mt-2 rounded-lg bg-violet-50 p-3 text-sm text-violet-700 dark:bg-violet-500/10 dark:text-violet-300">You were invited to a workspace. Use the email the invite was sent to.</p>}
        <div className="mt-6 space-y-4">
          <input required placeholder="Full name" value={form.full_name} onChange={set('full_name')} className={input} />
          <input required type="email" placeholder="Work email" value={form.email} onChange={set('email')} className={input} />
          {!invite && <input placeholder="Agency / workspace name (optional)" value={form.workspace_name} onChange={set('workspace_name')} className={input} />}
          <input required type="password" placeholder="Password (min 8 characters)" value={form.password} onChange={set('password')} className={input} />
          <input required type="password" placeholder="Confirm password" value={form.confirm} onChange={set('confirm')} className={input} />
        </div>
        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-600 dark:bg-red-500/10 dark:text-red-300">{error}</p>}
        {notice && <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">{notice}</p>}
        <button disabled={loading} className="mt-6 w-full rounded-xl bg-[#6D5DF6] py-3 text-sm font-bold text-white hover:bg-[#5b4ee4] disabled:opacity-60">
          {loading ? 'Creating account...' : 'Create account'}
        </button>
        <p className="mt-4 text-center text-sm text-slate-500 dark:text-[#8E8BA3]">
          Already have an account? <Link href="/login" className="font-bold text-[#6D5DF6]">Log in</Link>
        </p>
      </form>
    </main>
  );
}

export default function SignupPage() {
  return <Suspense fallback={null}><SignupForm /></Suspense>;
}
