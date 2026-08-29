"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  getPlaygroundKey,
  playgroundChat,
  playgroundEstimate,
  playgroundModels,
  setPlaygroundKey,
  type AutopilotMeta,
  type ChatMessage,
} from "@/lib/api";

type Turn = {
  role: "user" | "assistant" | "system";
  content: string;
  meta?: AutopilotMeta | null;
};

const DEFAULT_MODELS = [
  { id: "autopilot/cheap", resolves_to: "gpt-4o-mini", provider: "openai" },
  { id: "autopilot/balanced", resolves_to: "gpt-4o", provider: "openai" },
  { id: "autopilot/quality", resolves_to: "claude-sonnet-4-20250514", provider: "anthropic" },
  { id: "autopilot/fast", resolves_to: "gemini-2.0-flash", provider: "google" },
];

export default function PlaygroundPage() {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("autopilot/cheap");
  const [models, setModels] = useState(DEFAULT_MODELS);
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a concise assistant. Prefer short, useful answers."
  );
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState<string>("");
  const [sessionCost, setSessionCost] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const key = getPlaygroundKey();
    setApiKey(key);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  useEffect(() => {
    if (!apiKey) return;
    playgroundModels(apiKey)
      .then((list) => {
        if (list.length) setModels(list);
      })
      .catch(() => {
        /* keep defaults when gateway offline */
      });
  }, [apiKey]);

  function saveKey() {
    setPlaygroundKey(apiKey.trim());
  }

  async function refreshEstimate(nextMessages: ChatMessage[]) {
    if (!apiKey.trim()) return;
    try {
      const est = await playgroundEstimate(apiKey.trim(), model, nextMessages, 256);
      setEstimate(
        `~$${est.estimated_cost_usd.toFixed(6)} · ${est.resolved_model} · ~${est.input_tokens} in tokens`
      );
    } catch {
      setEstimate("");
    }
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    if (!apiKey.trim()) {
      setError("Paste a virtual API key first (create one on API Keys).");
      return;
    }
    setError("");
    saveKey();

    const userTurn: Turn = { role: "user", content: text };
    const nextTurns = [...turns, userTurn];
    setTurns(nextTurns);
    setInput("");
    setBusy(true);

    const messages: ChatMessage[] = [];
    if (systemPrompt.trim()) {
      messages.push({ role: "system", content: systemPrompt.trim() });
    }
    for (const t of nextTurns) {
      if (t.role === "system") continue;
      messages.push({ role: t.role, content: t.content });
    }

    await refreshEstimate(messages);

    try {
      const { body, meta } = await playgroundChat({
        apiKey: apiKey.trim(),
        model,
        messages,
        max_tokens: 512,
      });
      const content =
        (body as { choices?: Array<{ message?: { content?: string } }> }).choices?.[0]
          ?.message?.content || "(empty response)";
      setTurns((prev) => [...prev, { role: "assistant", content, meta }]);
      const cost = Number(meta.cost_usd || 0);
      if (!Number.isNaN(cost)) setSessionCost((c) => c + cost);
    } catch (err) {
      setError(String((err as Error).message || err));
      setTurns((prev) => prev.slice(0, -1));
      setInput(text);
    } finally {
      setBusy(false);
    }
  }

  function clearChat() {
    setTurns([]);
    setSessionCost(0);
    setEstimate("");
    setError("");
  }

  return (
    <>
      <h1>Playground</h1>
      <p className="lead">
        Talk through the gateway. Each reply shows resolved model, cost, and
        cache status — the same path your apps use.
      </p>

      <section className="panel playground-setup">
        <div className="form-row">
          <label style={{ flex: 1, minWidth: "220px" }}>
            Virtual API key
            <input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onBlur={saveKey}
              placeholder="lca_…"
              autoComplete="off"
            />
          </label>
          <label>
            Model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id} → {m.resolves_to}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={clearChat}>
            Clear chat
          </button>
        </div>
        <label>
          System prompt
          <textarea
            className="system-box"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={2}
          />
        </label>
        <div className="meta-strip">
          <span>
            Session spend: <strong>${sessionCost.toFixed(6)}</strong>
          </span>
          {estimate ? <span className="mono muted">{estimate}</span> : null}
        </div>
      </section>

      {error ? <p className="error">{error}</p> : null}

      <section className="chat-stage" aria-live="polite">
        {!turns.length ? (
          <p className="empty chat-empty">
            Send a message to run a live Autopilot completion. Try the same
            prompt twice to see a cache hit.
          </p>
        ) : (
          turns.map((t, i) => (
            <article key={i} className={`bubble ${t.role}`}>
              <header>{t.role}</header>
              <p>{t.content}</p>
              {t.meta ? (
                <footer className="bubble-meta">
                  <span className="badge">{t.meta.cache || "—"}</span>
                  <span className="mono">${t.meta.cost_usd ?? "—"}</span>
                  <span className="mono">{t.meta.model_used}</span>
                  {t.meta.provider ? <span>{t.meta.provider}</span> : null}
                  {t.meta.budget_alert ? (
                    <span className="badge warn">budget</span>
                  ) : null}
                </footer>
              ) : null}
            </article>
          ))
        )}
        {busy ? <p className="empty">Waiting on gateway…</p> : null}
        <div ref={bottomRef} />
      </section>

      <form className="composer" onSubmit={onSend}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message Autopilot…"
          rows={3}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend(e as unknown as FormEvent);
            }
          }}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </>
  );
}
