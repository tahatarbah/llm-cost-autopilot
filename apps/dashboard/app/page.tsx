"use client";

import { useEffect, useState } from "react";
import {
  adminFetch,
  getOrgId,
  type Org,
  type SpendSummary,
} from "@/lib/api";

function money(n: number) {
  return `$${n.toFixed(4)}`;
}

export default function OverviewPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [spend, setSpend] = useState<SpendSummary | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    adminFetch<Org[]>("/admin/orgs")
      .then((data) => {
        setOrgs(data);
        const saved = getOrgId();
        const pick = saved && data.some((o) => o.id === saved) ? saved : data[0]?.id || "";
        setOrgId(pick);
        if (pick) localStorage.setItem("lca_org_id", pick);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    localStorage.setItem("lca_org_id", orgId);
    adminFetch<SpendSummary>(`/admin/orgs/${orgId}/spend`)
      .then(setSpend)
      .catch((e) => setError(String(e.message || e)));
  }, [orgId]);

  return (
    <>
      <h1>Overview</h1>
      <p className="lead">
        Live spend across projects. Point apps at the gateway — or try the{" "}
        <a href="/playground">Playground</a> — and watch cost, cache hits, and
        budget headroom update here.
      </p>

      {error ? <p className="error">{error}</p> : null}

      <div className="form-row">
        <label>
          Organization
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            disabled={!orgs.length}
          >
            {!orgs.length ? <option value="">No orgs — run seed CLI</option> : null}
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid">
        <div className="stat">
          <div className="label">Today</div>
          <div className="value">{spend ? money(spend.today_usd) : "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Month to date</div>
          <div className="value">{spend ? money(spend.month_usd) : "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Requests (MTD)</div>
          <div className="value">{spend ? spend.request_count : "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Cache hit rate</div>
          <div className="value">
            {spend ? `${(spend.cache_hit_rate * 100).toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>

      <section className="panel">
        <h2>Spend by model</h2>
        {!spend?.by_model?.length ? (
          <p className="empty">No usage yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Requests</th>
                <th>Tokens</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {spend.by_model.map((row) => (
                <tr key={row.model}>
                  <td className="mono">{row.model}</td>
                  <td>{row.requests}</td>
                  <td>
                    {row.input_tokens + row.output_tokens}
                  </td>
                  <td>{money(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>Spend by project</h2>
        {!spend?.by_project?.length ? (
          <p className="empty">No project spend yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Project</th>
                <th>Requests</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {spend.by_project.map((row) => (
                <tr key={row.project_id}>
                  <td>{row.project}</td>
                  <td>{row.requests}</td>
                  <td>{money(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
