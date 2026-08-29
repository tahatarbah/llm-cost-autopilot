import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Cost Autopilot",
  description: "Observe and control LLM spend",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="top">
            <div className="brand">
              <span className="mark" aria-hidden />
              <div>
                <p className="product">LLM Cost Autopilot</p>
                <p className="tag">Spend control plane</p>
              </div>
            </div>
            <nav className="nav">
              <a href="/playground">Playground</a>
              <a href="/">Overview</a>
              <a href="/usage">Usage</a>
              <a href="/budgets">Budgets</a>
              <a href="/keys">API Keys</a>
              <a href="/settings">Settings</a>
            </nav>
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
