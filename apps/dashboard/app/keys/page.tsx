"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  adminFetch,
  getOrgId,
  setPlaygroundKey,
  type ApiKey,
  type Project,
} from "@/lib/api";

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("dashboard");
  const [created, setCreated] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function reload() {
    const id = getOrgId();
    if (!id) {
      setError("Select an organization on Overview first.");
      return;
    }
    const [k, p] = await Promise.all([
      adminFetch<ApiKey[]>(`/admin/orgs/${id}/api-keys`),
      adminFetch<Project[]>(`/admin/orgs/${id}/projects`),
    ]);
    setKeys(k);
    setProjects(p);
    if (!projectId && p[0]) setProjectId(p[0].id);
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCreated(null);
    try {
      const key = await adminFetch<ApiKey>("/admin/api-keys", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, name }),
      });
      setCreated(key.key || null);
      if (key.key) setPlaygroundKey(key.key);
      await reload();
    } catch (err) {
      setError(String((err as Error).message || err));
    }
  }

  async function onRevoke(id: string) {
    setError("");
    try {
      await adminFetch(`/admin/api-keys/${id}`, { method: "DELETE" });
      await reload();
    } catch (err) {
      setError(String((err as Error).message || err));
    }
  }

  return (
    <>
      <h1>API Keys</h1>
      <p className="lead">
        Virtual keys bind apps to a project. Use as{" "}
        <span className="mono">Authorization: Bearer lca_…</span> or paste into{" "}
        <a href="/playground">Playground</a>.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {created ? (
        <section className="panel">
          <h2>New key (copy now)</h2>
          <p className="mono">{created}</p>
          <p className="empty">
            Saved to Playground automatically.{" "}
            <a href="/playground">Open Playground →</a>
          </p>
        </section>
      ) : null}

      <section className="panel">
        <h2>Create key</h2>
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
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <button type="submit">Create</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Keys</h2>
        {!keys.length ? (
          <p className="empty">No keys yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Prefix</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td>{k.name}</td>
                  <td className="mono">{k.prefix}…</td>
                  <td>{new Date(k.created_at).toLocaleString()}</td>
                  <td>
                    <button type="button" className="linkish" onClick={() => onRevoke(k.id)}>
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
