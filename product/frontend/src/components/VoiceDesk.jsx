import React, { useCallback, useEffect, useRef, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { api } from "../api.js";

// Agent ids are not secret. Fallback lets teammates run without .env.local.
const AGENT_ID = import.meta.env.VITE_ELEVENLABS_AGENT_ID || "agent_4901m5qgkgf3e4js02cfx2jp1mqp";

function compact(p, i) {
  return {
    ordinal: i + 1,
    id: p.id,
    buyer: p.buyer,
    seller: p.seller,
    amount_usd: p.amount_usd,
    buys: p.purpose,
    flags: p.flags || [],
    blocked: !!p.blocked,
  };
}

async function decideTool(id, decision, reason, onDecided) {
  if (!id) return "Error: proposal_id is required.";
  try {
    const r = await api.decide(id, decision, reason || "");
    onDecided?.();
    return `${decision === "approve" ? "Approved" : "Rejected"} ${id}. Status: ${r.status || "done"}.`;
  } catch (e) {
    return `Error: could not ${decision} ${id}. ${e.message}`;
  }
}

function Panel({ onDecided }) {
  const [lines, setLines] = useState([]);
  const logRef = useRef(null);
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);
  const [err, setErr] = useState("");

  const conv = useConversation({
    clientTools: {
      get_pending_proposals: async () => {
        try {
          const list = await api.proposals("pending");
          return JSON.stringify(list.map(compact));
        } catch (e) {
          return `Error: could not read the queue. ${e.message}`;
        }
      },
      approve_proposal: ({ proposal_id }) => decideTool(proposal_id, "approve", "", onDecided),
      reject_proposal: ({ proposal_id, reason }) => decideTool(proposal_id, "reject", reason, onDecided),
    },
    onMessage: (m) => {
      const text = m?.message ?? m?.text;
      if (!text) return;
      const who = m.source === "user" || m.role === "user" ? "You" : "Desk";
      setLines((prev) => [...prev.slice(-49), { who, text }]);
    },
    onError: (e) => setErr(typeof e === "string" ? e : "The voice agent is unreachable. Check your connection."),
  });

  const live = conv.status === "connected";
  const busy = conv.status === "connecting";

  const toggle = useCallback(async () => {
    setErr("");
    if (live || busy) {
      conv.endSession();
      return;
    }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((t) => t.stop());
    } catch {
      setErr("Microphone access was blocked. Allow it in the browser and try again.");
      return;
    }
    try {
      await conv.startSession({ agentId: AGENT_ID, connectionType: "webrtc" });
    } catch {
      setErr("Could not reach the voice agent. Check your connection.");
    }
  }, [conv, live, busy]);

  const status = busy ? "Connecting" : live ? (conv.isSpeaking ? "Speaking" : "Listening") : "Off";

  return (
    <section className="voice-desk">
      <div className="voice-desk-row">
        <button className={`voice-pill${live ? " on" : ""}`} onClick={toggle} disabled={busy}>
          <span className={`voice-dot${live && conv.isSpeaking ? " pulse" : ""}${live ? " live" : ""}`} aria-hidden="true" />
          {live ? "End call" : busy ? "Connecting…" : "Talk to the desk"}
        </button>
        <span className="voice-status">MIC · {status.toUpperCase()}</span>
      </div>
      {err ? <div className="voice-line voice-err">{err}</div> : null}
      {lines.length ? (
        <div className="voice-log" ref={logRef} aria-live="polite">
          {lines.map((l, i) => (
            <p key={i} className={`voice-msg${l.who === "You" ? " you" : ""}`}>
              <span className="voice-who">{l.who}</span> {l.text}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function VoiceDesk({ onDecided }) {
  return (
    <ConversationProvider>
      <Panel onDecided={onDecided} />
    </ConversationProvider>
  );
}
