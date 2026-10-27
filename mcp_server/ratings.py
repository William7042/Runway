"""Verified buyer reviews; cannot be written using seller credentials."""
from . import queue_http as q


def install(mcp):
    @mcp.tool()
    def rate_specialist_job(job_id: str, stars: int, review: str = '', buyer_token: str = '') -> dict:
        """Rate a completed real paid job from 1–5. Requires the private job buyer token.

        One review per job. Simulated, unpaid, unfinished, and self-purchased work
        cannot receive a verified rating. Never print buyer tokens.
        """
        from .delivery_credentials import token
        buyer_token = buyer_token or token(job_id)
        if not buyer_token:
            raise ValueError('This buyer needs its saved private job access token')
        return q._req('POST', f'/specialist-jobs/{job_id}/rating',
                      json={'buyer_token': buyer_token, 'stars': stars, 'review': review})

    @mcp.tool()
    def list_specialist_reviews(specialist_id: str) -> list:
        """Read buyer reviews backed by completed real purchases."""
        return q._req('GET', f'/specialists/{specialist_id}/reviews')
