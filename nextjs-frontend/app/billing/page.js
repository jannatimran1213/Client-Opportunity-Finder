'use client';
// Module 1 - Subscription & Pricing Engine: Basic / Pro / Enterprise, monthly or yearly, usage limits,
// payment-gateway simulation (test mode) or real Stripe Checkout (BILLING_MODE=stripe).
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api, fmtDate } from '../lib/client';
import { useToast } from '../components/ToastProvider';
import { Badge, Button, Card, PageHeader, Progress, Table } from '../components/ui';

const LABELS = { leads: 'Leads', members: 'Team seats', pages: 'Hosted pages', emails: 'Emails / month', ai_generations: 'AI generations / month',
  audits: 'Audits / month', whatsapp: 'WhatsApp / month', linkedin: 'LinkedIn actions / month' };

function Billing() {
  const toast = useToast();
  const params = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [data, setData] = useState(null);
  const [payments, setPayments] = useState([]);
  const [interval, setInterval] = useState('monthly');
  const [busy, setBusy] = useState('');

  async function load() {
    try {
      const [p, s, pay] = await Promise.all([api('/billing/plans'), api('/billing/subscription'), api('/billing/payments')]);
      setPlans(p.plans); setData(s); setPayments(pay.payments || []);
      if (s.subscription?.interval) setInterval(s.subscription.interval);
    } catch (e) { toast(e.message, 'error'); }
  }
  useEffect(() => {
    load();
    if (params.get('status') === 'success') toast('Payment received, your plan is active', 'success');
    if (params.get('status') === 'cancelled') toast('Checkout cancelled', 'warning');
  }, []);

  async function choose(plan) {
    setBusy(plan);
    try {
      const r = await api('/billing/checkout', { method: 'POST', body: { plan, interval } });
      if (r.checkout_url) { window.location.href = r.checkout_url; return; }
      toast(`Switched to ${plan} (${interval}) - test payment recorded`, 'success');
      load();
    } catch (e) { toast(e.message, 'error'); } finally { setBusy(''); }
  }
  async function cancel() {
    if (!confirm('Cancel the subscription?')) return;
    try { await api('/billing/cancel', { method: 'POST' }); toast('Subscription cancelled', 'success'); load(); } catch (e) { toast(e.message, 'error'); }
  }
  async function portal() {
    try { const r = await api('/billing/portal', { method: 'POST' }); if (r.url) window.location.href = r.url; } catch (e) { toast(e.message, 'error'); }
  }

  const sub = data?.subscription;
  return (
    <div className="space-y-6">
      <PageHeader module="[1] Sign Up & SaaS Access" title="Subscription Engine"
        subtitle={data?.mode === 'test' ? 'Payment gateway simulation is ON (BILLING_MODE=test): plan changes apply instantly, no card needed.' : 'Payments are processed by Stripe Checkout.'}
        actions={sub && <>
          {data.mode !== 'test' && sub.stripe_customer_id && <Button variant="secondary" onClick={portal}>Manage card & invoices</Button>}
          {sub.status !== 'canceled' && <Button variant="ghost" onClick={cancel}>Cancel subscription</Button>}
        </>} />

      {sub && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-lg font-bold text-slate-900 dark:text-white">{sub.plan_name}</span>
            <Badge color={sub.status === 'active' ? 'green' : sub.status === 'trialing' ? 'blue' : 'red'}>{sub.status}</Badge>
            <Badge>{sub.interval}</Badge>
            {sub.trial_ends_at && sub.status === 'trialing' && <span className="text-sm text-slate-500">Trial ends {fmtDate(sub.trial_ends_at, false)}</span>}
            {sub.current_period_end && <span className="text-sm text-slate-500">Renews {fmtDate(sub.current_period_end, false)}</span>}
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-4">
            {Object.keys(LABELS).map((k) => (
              <div key={k}>
                <div className="mb-1 flex justify-between text-xs"><span className="font-bold text-slate-600 dark:text-[#C8C4E8]">{LABELS[k]}</span>
                  <span className="text-slate-400">{data.usage?.[k] ?? 0} / {data.limits?.[k]}</span></div>
                <Progress value={data.usage?.[k] ?? 0} max={data.limits?.[k]} />
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex justify-center">
        <div className="inline-flex rounded-xl border border-slate-200 p-1 dark:border-white/10">
          {['monthly', 'yearly'].map((i) => (
            <button key={i} onClick={() => setInterval(i)}
              className={`rounded-lg px-5 py-2 text-sm font-bold ${interval === i ? 'bg-[#6D5DF6] text-white' : 'text-slate-500'}`}>
              {i === 'monthly' ? 'Monthly' : 'Yearly (2 months free)'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        {plans.map((p) => {
          const current = sub?.plan === p.slug && sub?.interval === interval && sub?.status !== 'canceled';
          return (
            <Card key={p.slug} className={p.slug === 'pro' ? 'ring-2 ring-[#6D5DF6]' : ''}>
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">{p.name}</h3>
                {p.slug === 'pro' && <Badge color="purple">Most popular</Badge>}
              </div>
              <p className="mt-1 text-sm text-slate-500 dark:text-[#8E8BA3]">{p.description}</p>
              <p className="mt-4 text-4xl font-extrabold text-slate-900 dark:text-white">
                ${interval === 'yearly' ? p.price_yearly : p.price}<span className="text-base font-medium text-slate-400">/{interval === 'yearly' ? 'year' : 'month'}</span>
              </p>
              {p.trial_days > 0 && <p className="text-xs font-bold text-emerald-600">{p.trial_days}-day free trial</p>}
              <ul className="mt-4 space-y-1.5 text-sm text-slate-600 dark:text-[#C8C4E8]">
                {p.features.map((f) => <li key={f}>✓ {f}</li>)}
              </ul>
              <Button className="mt-6 w-full" variant={current ? 'secondary' : 'primary'} disabled={current} loading={busy === p.slug} onClick={() => choose(p.slug)}>
                {current ? 'Current plan' : `Choose ${p.name}`}
              </Button>
            </Card>
          );
        })}
      </div>

      <Card title="Payment history">
        <Table rows={payments} empty="No payments yet" columns={[
          { label: 'Date', render: (r) => fmtDate(r.date) }, { label: 'Plan', key: 'plan' },
          { label: 'Amount', render: (r) => `$${r.amount} ${r.currency || ''}` },
          { label: 'Status', render: (r) => <Badge color={r.status === 'completed' ? 'green' : 'amber'}>{r.status === 'test' ? 'test payment' : r.status}</Badge> },
          { label: 'Reference', render: (r) => <span className="font-mono text-xs">{r.transaction_id}</span> }]} />
      </Card>
    </div>
  );
}

export default function BillingPage() { return <Suspense fallback={null}><Billing /></Suspense>; }
