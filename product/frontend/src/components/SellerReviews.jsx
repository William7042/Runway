import React, { useEffect, useState } from "react";
import WriteReview from "./WriteReview.jsx";

export default function SellerReviews({ specialist, api, refreshKey }) {
  const [open, setOpen] = useState(false);
  const [writing, setWriting] = useState(false);
  const [updated, setUpdated] = useState(0);
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    let alive = true;
    api.specialistReviews(specialist.id).then(r => {
      if (alive) { setReviews(r); setError(""); }
    }).catch(e => alive && setError(e.message));
    return () => { alive = false; };
  }, [open, specialist.id, specialist.rating_count, refreshKey, api, updated]);
  const count = specialist.rating_count || 0;
  return (
    <div className="seller-reviews">
      <button className="btn small" disabled={!count} onClick={() => setOpen(!open)} aria-expanded={open}>
        {count ? `★ ${Number(specialist.rating_average).toFixed(1)} / 5 · ${count} verified review${count === 1 ? "" : "s"}` : "No verified reviews yet"}
      </button>
      {!specialist.simulated && <button className="btn small" onClick={() => setWriting(!writing)} aria-expanded={writing}>
        {writing ? 'Cancel review' : 'Write a review'}
      </button>}
      {writing && <WriteReview specialist={specialist} api={api} onSubmitted={() => { setOpen(true); setUpdated(n => n + 1); }} />}
      {open && <div className="stack">
        {error && <p className="error">{error}</p>}
        {reviews.map(r => <blockquote key={r.job_id}>
          <div><strong>{"★".repeat(r.stars)}{"☆".repeat(5-r.stars)}</strong> · {r.buyer} · Verified purchase</div>
          {r.review && <p>{r.review}</p>}
        </blockquote>)}
      </div>}
    </div>
  );
}
