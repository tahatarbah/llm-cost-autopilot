"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  adminFetch,
  getOrgId,
  type Budget,
  type Project,
} from "@/lib/api";

export default function BudgetsPage() {
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState("50");
  const [period, setPeriod] = useState("monthly");
  const [action, setAction] = useState("block");
  const [projectId, setProjectId] = useState("");

  const orgId = typeof window !== "undefined" ? getOrgId() : null;

  async function reload() {
    const id = getOrgId();
    if (!id) {
      setError("Select an organization on Overview first.");
      return;
    }
    const [b, p] = await Promise.all([
      adminFetch<Budget[]>(`/admin/orgs/${id}/budgets`),
      adminFetch<Project[]>(`/admin/orgs/${id}/projects`),
    ]);
    setBudgets(b);
    setProjects(p);
    if (!projectId && p[0]) setProjectId(p[0].id);
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const id = getOrgId();
    if (!id) return;
    setError("");
    try {
      await adminFetch(`/admin/budgets?org_id=${id}`, {
        method: "POST",
        body: JSON.stringify({
          scope: "project",
          project_id: projectId || null,
          period,
          limit_usd: Number(limit),
          action,
          alert_threshold: 0.8,
        }),
      });
      await reload();
    } catch (err) {
      setError(String((err as Error).message || err));
    }
  }

  return (
    <>
      <h1>Budgets</h1>
      <p className="lead">
        Cap spend per project. Block returns HTTP 402 from the gateway when the
        limit is hit.
      </p>
      {error ? <p className="error">{error}</p> : null}

      <section className="panel">
        <h2>Create budget</h2>
        <form onSubmit={onCreate}>
          <div className="form-row">
            <label>
              Project
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Period
              <select value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="daily">daily</option>
                <option value="monthly">monthly</option>
              </select>
            </label>
            <label>
              Limit (USD)
              <input value={limit} onChange={(e) => setLimit(e.target.value)} />
            </label>
            <label>
              Action
              <select value={action} onChange={(e) => setAction(e.target.value)}>
                <option value="block">block</option>
                <option value="alert">alert</option>
              </select>
            </label>
            <button type="submit">Add budget</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Active budgets</h2>
        {!budgets.length ? (
          <p className="empty">No budgets configured.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Period</th>
                <th>Limit</th>
                <th>Spent</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {budgets.map((b) => (
                <tr key={b.id}>
                  <td>{b.scope}</td>
                  <td>{b.period}</td>
                  <td>${b.limit_usd.toFixed(2)}</td>
                  <td>
                    ${b.spent_usd.toFixed(4)}
                    {b.spent_usd >= b.limit_usd ? (
                      <>
                        {" "}
                        <span className="badge danger">exceeded</span>
                      </>
                    ) : b.spent_usd >= b.limit_usd * b.alert_threshold ? (
                      <>
                        {" "}
                        <span className="badge warn">alert</span>
                      </>
                    ) : null}
                  </td>
                  <td>{b.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {!orgId ? null : null}
    </>
  );
}
