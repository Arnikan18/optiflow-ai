import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { DemoCustomer, DemoPortfolio } from '../../types/api';

function formatMoney(value: number | null): string {
  if (value === null) return '—';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}m`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${Math.round(value)}`;
}

function CustomerSignal({
  customer,
  portfolio,
}: {
  customer: DemoCustomer;
  portfolio: DemoPortfolio;
}) {
  const incidents = portfolio.incidents.filter(
    (incident) => incident.customer_id === customer.customer_id,
  );
  const slaRiskCount = incidents.filter((incident) => incident.sla_risk).length;

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-3 border-b border-border-dim last:border-0">
      <div className="min-w-0">
        <p className="text-xs font-bold text-ink-primary truncate">{customer.customer_name}</p>
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {customer.renewal_risk && (
            <span className="text-[8px] font-mono uppercase tracking-wider text-ops-violet">
              renewal risk
            </span>
          )}
          {incidents.length > 0 && (
            <span className="text-[8px] font-mono uppercase tracking-wider text-ops-rose">
              {incidents.length} incident{incidents.length === 1 ? '' : 's'}
            </span>
          )}
          {slaRiskCount > 0 && (
            <span className="text-[8px] font-mono uppercase tracking-wider text-ops-orange">
              SLA pressure
            </span>
          )}
        </div>
      </div>
      <span className="text-xs font-mono font-semibold text-ink-secondary">
        {formatMoney(customer.arr)}
      </span>
    </li>
  );
}

export function PortfolioPulse() {
  const [portfolio, setPortfolio] = useState<DemoPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeLens, setActiveLens] = useState<'customers' | 'incidents' | 'capacity'>('customers');

  const loadPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      setPortfolio(await api.getDemoPortfolio());
      setError(null);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Portfolio context is unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  const riskCustomers = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.customers
      .filter((customer) => {
        const incidents = portfolio.incidents.filter(
          (incident) => incident.customer_id === customer.customer_id,
        );
        return customer.renewal_risk || incidents.some((incident) => incident.sla_risk);
      })
      .sort((left, right) => (right.arr ?? 0) - (left.arr ?? 0))
      .slice(0, 4);
  }, [portfolio]);

  if (loading && !portfolio) {
    return (
      <section className="border-b border-border-dim bg-abyss" aria-label="Loading portfolio context">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-6">
          <div className="h-5 w-48 rounded bg-surface animate-pulse" />
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 mt-5">
            {Array.from({ length: 5 }, (_, index) => (
              <div key={index} className="h-24 rounded-2xl bg-deep animate-pulse" />
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error && !portfolio) {
    return (
      <section className="border-b border-ops-rose/20 bg-ops-rose/5">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold text-ops-rose">Live portfolio context could not be loaded.</p>
            <p className="text-[10px] text-ink-muted mt-1">{error}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadPortfolio()}
            className="text-xs font-semibold text-ops-rose hover:underline focus-ring rounded"
          >
            Try again
          </button>
        </div>
      </section>
    );
  }

  if (!portfolio) return null;

  const summary = portfolio.portfolio_summary;
  const arrRiskRatio = summary.total_arr_represented
    ? Math.min(100, Math.round(((summary.total_arr_at_risk ?? 0) / summary.total_arr_represented) * 100))
    : 0;
  const availableRatio = summary.total_specialists
    ? Math.min(100, Math.round(((summary.available_specialists ?? 0) / summary.total_specialists) * 100))
    : 0;
  const maximumArr = Math.max(...portfolio.customers.map((customer) => customer.arr ?? 0), 1);
  const metrics = [
    {
      label: 'ARR at risk',
      value: formatMoney(summary.total_arr_at_risk),
      detail: `${arrRiskRatio}% of represented revenue`,
      color: 'text-ops-rose',
    },
    {
      label: 'Active incidents',
      value: summary.total_active_incidents ?? '—',
      detail: `${summary.total_at_risk_customers ?? 0} customers at risk`,
      color: 'text-ops-orange',
    },
    {
      label: 'Near SLA breach',
      value: summary.incidents_near_sla_breach ?? '—',
      detail: 'Time-sensitive evidence',
      color: 'text-ops-amber',
    },
    {
      label: 'Unassigned',
      value: summary.unassigned_incidents ?? '—',
      detail: 'Needs an ownership decision',
      color: 'text-ops-violet',
    },
    {
      label: 'Available team',
      value: `${summary.available_specialists ?? 0}/${summary.total_specialists ?? 0}`,
      detail: `${Math.round(summary.average_workload ?? 0)}% average workload`,
      color: 'text-ops-cyan',
    },
  ];

  return (
    <section className="border-b border-border-dim bg-abyss" aria-labelledby="portfolio-pulse-title">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 py-6 lg:py-8">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-ops-cyan" />
              <p className="text-[9px] font-mono font-semibold uppercase tracking-[0.2em] text-ops-cyan">
                Live decision context
              </p>
            </div>
            <h2 id="portfolio-pulse-title" className="text-xl sm:text-2xl font-extrabold tracking-[-0.04em] mt-2">
              See the pressure before choosing the goal.
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {(portfolio.degraded || summary.partial) && (
              <span className="text-[9px] font-mono uppercase tracking-wider text-ops-orange">
                Partial evidence
              </span>
            )}
            <button
              type="button"
              onClick={() => void loadPortfolio()}
              disabled={loading}
              className="text-[9px] font-mono font-semibold uppercase tracking-[0.14em] text-ink-muted hover:text-ops-cyan disabled:opacity-40 focus-ring rounded"
            >
              {loading ? 'Refreshing…' : 'Refresh context'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 mt-5">
          {metrics.map((metric) => (
            <article key={metric.label} className="rounded-2xl border border-border-dim bg-deep px-4 py-4">
              <p className="text-[9px] font-mono uppercase tracking-[0.14em] text-ink-muted">
                {metric.label}
              </p>
              <p className={`text-2xl sm:text-3xl font-extrabold tracking-[-0.05em] mt-2 ${metric.color}`}>
                {metric.value}
              </p>
              <p className="text-[10px] leading-relaxed text-ink-muted mt-1.5">{metric.detail}</p>
            </article>
          ))}
        </div>

        <div className="grid lg:grid-cols-[1.25fr_0.75fr] gap-3 mt-3">
          <article className="rounded-2xl border border-border-dim bg-abyss p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[9px] font-mono uppercase tracking-[0.16em] text-ink-muted">
                  Why a decision is needed
                </p>
                <p className="text-sm font-bold text-ink-primary mt-2">
                  Revenue exposure is high while ownership and capacity are constrained.
                </p>
              </div>
              <span className="text-[9px] font-mono text-ink-muted shrink-0">
                CRM + INCIDENT + WORKFORCE
              </span>
            </div>
            <div className="grid sm:grid-cols-2 gap-5 mt-5">
              <div>
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-ink-muted">Revenue exposure</span>
                  <span className="font-semibold text-ops-rose">{arrRiskRatio}%</span>
                </div>
                <div className="h-2 rounded-full bg-surface overflow-hidden mt-2">
                  <div className="h-full rounded-full bg-ops-rose" style={{ width: `${arrRiskRatio}%` }} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-ink-muted">Team currently available</span>
                  <span className="font-semibold text-ops-cyan">{availableRatio}%</span>
                </div>
                <div className="h-2 rounded-full bg-surface overflow-hidden mt-2">
                  <div className="h-full rounded-full bg-ops-cyan" style={{ width: `${availableRatio}%` }} />
                </div>
              </div>
            </div>
          </article>

          <article className="rounded-2xl border border-border-dim bg-deep p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[9px] font-mono uppercase tracking-[0.16em] text-ink-muted">
                Highest-value signals
              </p>
              <span className="text-[9px] font-mono text-ink-ghost">ARR</span>
            </div>
            <ul className="mt-2">
              {riskCustomers.length > 0 ? riskCustomers.map((customer) => (
                  <CustomerSignal
                    key={customer.customer_id}
                    customer={customer}
                    portfolio={portfolio}
                  />
                )) : (
                  <li className="py-6 text-center text-[10px] text-ink-muted">
                    No customer currently carries renewal or SLA risk.
                  </li>
                )}
            </ul>
          </article>
        </div>

        <div className="rounded-[1.5rem] border border-border-dim bg-deep/45 p-5 sm:p-6 mt-3">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
            <div>
              <p className="text-[9px] font-mono uppercase tracking-[0.16em] text-ink-muted">
                Pressure explorer
              </p>
              <h3 className="text-base font-extrabold tracking-[-0.025em] text-ink-primary mt-1.5">
                See which facts create the recommendation pressure.
              </h3>
            </div>
            <div className="grid grid-cols-3 gap-2" role="tablist" aria-label="Portfolio pressure lenses">
              {([
                ['customers', 'Customers'],
                ['incidents', 'Incidents'],
                ['capacity', 'Capacity'],
              ] as const).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={activeLens === id}
                  onClick={() => setActiveLens(id)}
                  className={`rounded-lg border px-3 py-2 text-[9px] font-semibold focus-ring ${
                    activeLens === id
                      ? 'border-ops-cyan bg-ops-cyan/[0.07] text-ops-cyan'
                      : 'border-border-dim bg-abyss text-ink-muted hover:text-ink-primary'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {activeLens === 'customers' && (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5">
              {portfolio.customers.map((customer) => {
                const customerIncidents = portfolio.incidents.filter(
                  (incident) => incident.customer_id === customer.customer_id,
                );
                const pressure = customer.renewal_risk
                  || customerIncidents.some((incident) => incident.sla_risk);
                return (
                  <article key={customer.customer_id} className="rounded-xl border border-border-dim bg-abyss p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-ink-primary truncate">{customer.customer_name}</p>
                        <p className="text-[8px] font-mono uppercase tracking-[0.12em] text-ink-muted mt-1">
                          {customer.segment ?? customer.strategic_priority ?? 'segment not reported'}
                        </p>
                      </div>
                      <span className={`w-2 h-2 rounded-full mt-1 ${
                        pressure ? 'bg-ops-rose' : 'bg-ops-emerald'
                      }`} />
                    </div>
                    <div className="flex items-center justify-between text-[9px] font-mono mt-4">
                      <span className="text-ink-muted">ARR influence</span>
                      <span className="font-semibold text-ink-secondary">{formatMoney(customer.arr)}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface overflow-hidden mt-2">
                      <div
                        className={`h-full rounded-full ${pressure ? 'bg-ops-rose' : 'bg-ops-cyan'}`}
                        style={{ width: `${Math.max(4, ((customer.arr ?? 0) / maximumArr) * 100)}%` }}
                      />
                    </div>
                    <p className="text-[9px] leading-relaxed text-ink-muted mt-3">
                      {customerIncidents.length} active incident signal{customerIncidents.length === 1 ? '' : 's'}
                      {customer.renewal_risk ? ' · renewal risk present' : ' · renewal stable'}
                    </p>
                  </article>
                );
              })}
            </div>
          )}

          {activeLens === 'incidents' && (
            <div className="grid md:grid-cols-2 gap-3 mt-5">
              {portfolio.incidents.map((incident) => (
                <article key={incident.incident_id} className="rounded-xl border border-border-dim bg-abyss p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[9px] font-mono text-ink-muted">{incident.incident_id}</span>
                    <span className={`rounded-full px-2 py-1 text-[8px] font-mono font-semibold uppercase ${
                      incident.sla_risk
                        ? 'bg-ops-rose/10 text-ops-rose'
                        : 'bg-ops-emerald/10 text-ops-emerald'
                    }`}>
                      {incident.sla_risk ? 'SLA pressure' : 'within SLA'}
                    </span>
                  </div>
                  <p className="text-xs font-bold text-ink-primary mt-3">{incident.title ?? incident.summary ?? 'Untitled incident'}</p>
                  <div className="grid grid-cols-2 gap-3 mt-4 text-[9px]">
                    <div>
                      <p className="font-mono uppercase tracking-[0.11em] text-ink-muted">Severity</p>
                      <p className="font-semibold text-ink-secondary mt-1">{incident.severity ?? 'not reported'}</p>
                    </div>
                    <div>
                      <p className="font-mono uppercase tracking-[0.11em] text-ink-muted">Ownership</p>
                      <p className="font-semibold text-ink-secondary mt-1">
                        {incident.current_specialist_id ?? 'Unassigned'}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-4 pt-3 border-t border-border-dim">
                    {incident.required_skills.map((skill) => (
                      <span key={skill} className="rounded-full border border-border-dim bg-deep px-2 py-1 text-[8px] text-ink-muted">
                        {skill}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}

          {activeLens === 'capacity' && (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5">
              {portfolio.specialists.map((specialist) => {
                const utilisation = Math.max(0, Math.min(100, specialist.utilisation_percentage ?? 0));
                const available = specialist.availability === true;
                return (
                  <article key={specialist.specialist_id} className="rounded-xl border border-border-dim bg-abyss p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-ink-primary">{specialist.specialist_name}</p>
                        <p className="text-[8px] font-mono text-ink-muted mt-1">{specialist.specialist_id}</p>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-[8px] font-mono ${
                        available ? 'bg-ops-emerald/10 text-ops-emerald' : 'bg-surface text-ink-muted'
                      }`}>
                        {available ? 'available' : 'unavailable'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[9px] font-mono mt-4">
                      <span className="text-ink-muted">Utilisation</span>
                      <span className={utilisation >= 80 ? 'text-ops-rose' : 'text-ops-cyan'}>{Math.round(utilisation)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface overflow-hidden mt-2">
                      <div
                        className={`h-full rounded-full ${utilisation >= 80 ? 'bg-ops-rose' : 'bg-ops-cyan'}`}
                        style={{ width: `${utilisation}%` }}
                      />
                    </div>
                    <p className="text-[9px] leading-relaxed text-ink-muted mt-3">
                      Workload {specialist.current_workload ?? 0}/{specialist.capacity ?? 0}
                      {' · '}{specialist.skills.slice(0, 3).join(', ') || 'skills not reported'}
                    </p>
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <p className="text-[10px] leading-relaxed text-ink-muted mt-3">
          These signals set context only. The route will still validate constraints, compare alternatives,
          and stop for human approval before any operational change.
        </p>
      </div>
    </section>
  );
}
