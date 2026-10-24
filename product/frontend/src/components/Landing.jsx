import React from "react";
import "../styles/landing.css";

const PROBLEMS = [
  {
    n: "01",
    title: "Agents can't buy anything",
    body: "Paywalls, subscriptions and human-only services all assume a person with a credit card. Every time an agent needs data or help, it stalls and pings a human.",
  },
  {
    n: "02",
    title: "Cash budgets sit idle",
    body: "Giving an agent a stablecoin budget means selling the assets you actually want to hold, then leaving that money uninvested.",
  },
  {
    n: "03",
    title: "A wallet is an attack surface",
    body: "One hidden instruction on a web page can talk an agent with a wallet into sending everything. Autonomy without hard limits isn't safe.",
  },
];

const STEPS = [
  { title: "Agent proposes", body: "It explains in plain English what it wants to buy and why." },
  { title: "Policy checks", body: "Spend caps, allowlists and injection detection run in code. Bad orders are blocked before you see them." },
  { title: "You decide", body: "One card, one decision. Approve or reject. There is no auto-approve." },
  { title: "Router pays", body: "It pays in kind, or sells only what's needed at the best quote, and signs locally." },
  { title: "Receipt", body: "Every payment is logged with what was sold, the quote, the fill and the transaction." },
];

const DIFFS = [
  { title: "Spend from a portfolio, not a cash pile", body: "The treasury stays invested, for example in tokenized Nvidia. Endowment mode only spends gains, so the principal is never touched." },
  { title: "A human on every order", body: "Agents propose, people decide. Every order needs an explicit approval, with the reason and the cost shown up front." },
  { title: "Guardrails the model can't argue with", body: "Limits are plain code, not prompts. A second model checks each order against what you actually asked for." },
  { title: "Pays in whatever the seller wants", body: "The router compares paying in kind against swapping, checks price drift on tokenized stocks, and picks the cheapest safe path." },
];

const STACK = ["Wallets per agent", "Quotes and orders", "Local signing", "Transfers", "Price history"];

export default function Landing({ onOpen }) {
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-eyebrow">Runway</div>
        <h1>
          Let AI agents spend.
          <br />
          <span className="hero-accent">Keep a human on every order.</span>
        </h1>
        <p className="hero-sub">
          Runway is an economy for AI agents. They hold real assets, hire specialists and people, and pay in whatever they
          hold, while a person approves every order and the investments stay invested.
        </p>
        <div className="hero-cta">
          <button className="btn btn-primary btn-lg" onClick={onOpen}>
            Open approvals
          </button>
          <a className="btn btn-ghost btn-lg" href="#how">
            How it works
          </a>
        </div>
      </section>

      <section className="l-section">
        <div className="l-kicker">The problem</div>
        <h2 className="l-title">Agents can think. They can't pay.</h2>
        <div className="problem-grid">
          {PROBLEMS.map((p) => (
            <div key={p.n} className="problem">
              <div className="problem-n">{p.n}</div>
              <h3>{p.title}</h3>
              <p>{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="l-section" id="how">
        <div className="l-kicker">Our approach</div>
        <h2 className="l-title">Agents propose. People decide. Code enforces.</h2>
        <ol className="steps-row">
          {STEPS.map((s, i) => (
            <li key={s.title} className={`step-card ${s.title === "You decide" ? "step-key" : ""}`}>
              <div className="step-num">{i + 1}</div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="l-section">
        <div className="l-kicker">What makes us different</div>
        <h2 className="l-title">Built for agents that spend real money.</h2>
        <div className="diff-grid">
          {DIFFS.map((d) => (
            <div key={d.title} className="diff">
              <div className="diff-check" aria-hidden="true">✓</div>
              <div>
                <h3>{d.title}</h3>
                <p>{d.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="l-section stack">
        <div className="l-kicker">Built on the True Markets Gateway</div>
        <div className="stack-row">
          {STACK.map((s) => (
            <span key={s} className="stack-chip">
              {s}
            </span>
          ))}
        </div>
      </section>

      <section className="l-final">
        <h2>Every order. One decision. Yours.</h2>
        <button className="btn btn-mint btn-lg" onClick={onOpen}>
          Open approvals
        </button>
        <p className="l-disclaimer">Technical demo, not financial advice. Sellers in the demo are simulated and labelled.</p>
      </section>
    </div>
  );
}
