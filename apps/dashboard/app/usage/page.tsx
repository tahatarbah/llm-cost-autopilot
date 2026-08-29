"use client";

import { useEffect, useState } from "react";
import { adminFetch, getOrgId, type UsageEvent } from "@/lib/api";

export default function UsagePage() {
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const orgId = getOrgId();
    if (!orgId) {
      setError("Select an organization on Overview first (or run seed).");
      return;
    }
    adminFetch<UsageEvent[]>(`/admin/orgs/${orgId}/usage?limit=100`)
      .then(setEvents)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  return (
    <>
      <h1>Usage</h1>
      <p className="lead">Recent completion requests with cost and cache status.</p>
      {error ? <p className="error">{error}</p> : null}
      <section className="panel">
        {!events.length && !error ? (
          <p className="empty">No events yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Model</th>
                <th>Provider</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Cache</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.created_at).toLocaleString()}</td>
                  <td className="mono">{e.model}</td>
                  <td>{e.provider}</td>
                  <td>
                    {e.input_tokens}/{e.output_tokens}
                  </td>
                  <td>${e.cost_usd.toFixed(6)}</td>
                  <td>
                    {e.cache_hit ? (
                      <span className="badge">hit</span>
                    ) : (
                      <span className="badge warn">miss</span>
                    )}
                  </td>
                  <td>{e.latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
