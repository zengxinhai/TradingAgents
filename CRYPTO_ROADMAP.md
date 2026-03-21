# Crypto Trading Automation Roadmap

## Month 1 — Crypto Data Layer
Replace stock data sources with crypto-native equivalents. No agent logic changes.

- [ ] Wire price/OHLCV via **CCXT** (`dataflows/ccxt_crypto.py`)
- [ ] Add on-chain metrics via **Glassnode/Messari** — exchange inflows, whale activity, active addresses
- [ ] Add crypto news via **CryptoPanic API** — has built-in sentiment scoring
- [ ] Add social sentiment — Twitter/X, Reddit
- [ ] Add funding rates + open interest via Bybit/Binance API — critical for perps
- [ ] Add **On-Chain Analyst** agent — no stock equivalent; genuine retail edge
- [ ] Update Fundamentals Analyst prompt — swap P/E for tokenomics, TVL, protocol revenue

---

## Month 2 — Shadow Mode Paper Trading
Run framework alongside your real trades. Zero capital risk, real signal validation.

- [ ] Log framework signal vs. your decision vs. outcome for every trade
- [ ] After 4-6 weeks: identify where it's right, where it's wrong, and why
- [ ] Fix bad prompts; replace misleading data sources

> Skip backtesting for now — LLM data leakage + crypto regime changes make old backtests unreliable.

---

## Month 3 — Semi-Automated Execution
Framework does the analysis. You make the final call and execute.

- [ ] Build a simple dashboard surfacing the full framework output (debate summary, investment plan, risk perspectives)
- [ ] Wire execution via CCXT
- [ ] You replace the Risk Judge — until you trust the signal enough to automate it

---

## Month 4+ — Selective Automation
Automate only patterns you've validated. Keep human oversight for novel situations.

- [ ] Define automation rules from Month 2-3 learnings
- [ ] Add position sizing logic
- [ ] Add circuit breakers for black swan events
- [ ] Build backtesting with LLM response cache (cheap reruns) + portfolio simulator
- [ ] Use existing `reflect_and_remember()` as a continuous feedback loop
