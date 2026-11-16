'use client';
// Background jobs (Celery + Redis): scraping, audits, bulk AI writing, bulk sends and validation run here
// so the UI stays responsive. Falls back to in-process execution when no Celery worker is running.
import { useEffect, useState } from 'react';
import { api, fmtDate } from '../lib/client';
import { Badge, Button, Card, Modal, PageHeader, statusColor, Table } from '../components/ui';

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState(null);
  const load = () => api('/jobs').then((d) => setJobs(d.jobs || [])).catch(() => {});
  useEffect(() => {
    load(); api('/jobs/kinds').then(setInfo).catch(() => {});
    const t = setInterval(load, 4000); return () => clearInterval(t);
  }, []);
  return (
    <div className="space-y-6">
      <PageHeader module="Background processing" title="Background jobs"
        subtitle={info ? (info.celery_broker_available ? 'Celery + Redis broker connected: jobs run on Celery workers.' : 'Redis broker not reachable: jobs run inside the API process (fine for development).') : ''}
        actions={<Button variant="secondary" onClick={load}>Refresh</Button>} />
      <Card>
        <Table rows={jobs} empty="No jobs yet" columns={[{ label: 'Created', render: (j) => fmtDate(j.created_at) }, { label: 'Job', key: 'label' },
          { label: 'Status', render: (j) => <Badge color={statusColor(j.status)}>{j.status}</Badge> }, { label: 'Runner', render: (j) => <Badge>{j.runner || '-'}</Badge> },
          { label: 'Finished', render: (j) => fmtDate(j.finished_at) }, { label: 'Error', render: (j) => <span className="text-xs text-red-500">{j.error}</span> },
          { label: '', render: (j) => <Button variant="ghost" onClick={async () => setOpen(await api(`/jobs/${j.id}`))}>Details</Button> }]} />
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open?.label || ''} wide>
        {open && <pre className="max-h-[60vh] overflow-auto rounded-lg bg-slate-50 p-3 text-xs dark:bg-white/[0.03]">{JSON.stringify({ payload: open.payload, result: open.result, error: open.error }, null, 2)}</pre>}
      </Modal>
    </div>
  );
}
