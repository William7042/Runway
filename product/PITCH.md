# Runway pitch notes

## Teammate's pitch (transcribed 2026-10-24, lightly cleaned up)

> Mix of fintech and the SpaceX one. Our idea is built on the True Markets infrastructure, where you can trade hundreds of different coins and assets. We're making an economy for AI agents. Right now, if you want to buy something online, you need to put in your credit card information. There's no way for an agent to purchase something for you. So in our system there are specialty agents and human bounties, all in one place, and you can pay with whatever asset you want through the True Markets infrastructure. There's MCP too. Say you're building a stock trading bot and you need data for it...

Open question from the recording: someone said "402?". If that means HTTP 402 / x402 agent payments, decide whether it belongs in the pitch.

## Short README

# Runway

Runway lets AI agents pay for things. Today an agent can't buy anything online without a person typing in a credit card. With Runway, an agent holds real assets and spends them to hire specialist agents or post bounties for humans.

**Pay in any asset.** Runway runs on True Markets, so an agent can pay with any of hundreds of coins and assets it already holds. Its other investments stay invested.

**A person approves every order.** Each payment shows up in an approval queue with its cost, price drift, and the reason the agent asked for it. Policy rules block unsafe orders, such as ones triggered by a prompt injection, before anyone can approve them.

**Agents connect through MCP.** An agent building a stock trading bot can find a data provider, pay for the data, and get it back in the same session.

### Run the demo

See `product/README.md` and `product/DEMO_SCRIPT.md`. The demo runs with `DRY_RUN=1` and a stub executor, so it never signs or sends money.
