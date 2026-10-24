"""Person B — Agent layer for Runway.

Owns: research agent, mock sellers, specialist registry, bounty board,
policy checks, verifier, and the prompt-injection demo.

Does NOT call True Markets. All payments go through Person A's
propose_payment / execute router interface and Person C's approval queue.
"""

__version__ = "0.1.0"
