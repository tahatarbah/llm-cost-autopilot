"use client";

import { FormEvent, useEffect, useState } from "react";

export default function SettingsPage() {
  const [token, setToken] = useState("dev-secret-change-me");
  const [gateway, setGateway] = useState("http://localhost:8080");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem("lca_admin_token") || "dev-secret-change-me");
    setGateway(
      localStorage.getItem("lca_gateway_url") ||
        process.env.NEXT_PUBLIC_GATEWAY_URL ||
        "http://localhost:8080"
    );
  }, []);

  function onSave(e: FormEvent) {
    e.preventDefault();
    localStorage.setItem("lca_admin_token", token);
    localStorage.setItem("lca_gateway_url", gateway);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <>
      <h1>Settings</h1>
      <p className="lead">
        Admin token must match <span className="mono">GATEWAY_SECRET</span> on
        the gateway. For production, rotate this and never commit secrets.
      </p>
      <section className="panel">
        <form onSubmit={onSave}>
          <div className="form-row">
            <label>
              Admin token (X-Admin-Token)
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                style={{ minWidth: "280px" }}
              />
            </label>
            <label>
              Gateway URL (display only; rebuild for NEXT_PUBLIC change)
              <input
                value={gateway}
                onChange={(e) => setGateway(e.target.value)}
                style={{ minWidth: "280px" }}
              />
            </label>
            <button type="submit">Save</button>
          </div>
        </form>
        {saved ? <p className="empty">Saved locally.</p> : null}
      </section>
      <section className="panel">
        <h2>Seed reminder</h2>
        <p className="empty mono">
          llm-cost-seed --admin-email you@example.com
        </p>
      </section>
    </>
  );
}
