import React, { useEffect, useRef } from "react";

// CSS-only animated background plus a soft light that follows the cursor.
// No WebGL, so there is nothing to fall back from.
export default function Backdrop() {
  const glow = useRef(null);
  useEffect(() => {
    let raf = 0;
    const move = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        if (!glow.current) return;
        glow.current.style.setProperty("--mx", `${e.clientX}px`);
        glow.current.style.setProperty("--my", `${e.clientY}px`);
      });
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(raf);
    };
  }, []);
  return (
    <>
      <div className="backdrop" aria-hidden="true">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
        <div className="orb orb-c" />
        <div className="grid" />
        <div className="grain" />
      </div>
      <div className="cursor-glow" ref={glow} aria-hidden="true" />
    </>
  );
}
