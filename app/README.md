# Compliance Copilot Frontend

This frontend is the operator workspace for crypto compliance and investigations. It is designed to help analysts, AML teams, exchanges, OTC desks, and VIP risk operators move from wallet intake to decision quickly.

## What the UI covers

- Signed-out landing flow that explains what the product is, how teams use it, and why it is operationally valuable.
- Signed-in analyst workspace for wallet intelligence, watchlists, alerts, incidents, investigations, admin, and exports.
- Live Ethereum wallet enrichment and live counterparty clustering.
- Analyst-assisted scoring and workflow coverage for Solana, Base, Arbitrum, BSC, and Polygon inputs.

## Local development

Run the frontend from this directory:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:3000.

For the full product experience, run the backend from the repository root as well so the dashboard can authenticate and call live intelligence APIs.

## Local sign-in

Use one of these real local options instead of relying on seeded preview credentials:

- Sign up with your work email when the workspace is empty — the first signup becomes the owner/admin.
- Or sign in with an existing local workspace account already present in your current database.

Preview OAuth and phone flows stay hidden unless `NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=true` is explicitly enabled.

## Best local flows

The UI includes sample-wallet shortcuts for validated scenarios:

- Vitalik EOA wallet — good for low-risk live Ethereum enrichment and narrative output.
- Binance hot wallet — good for high-activity exchange behavior, watchlist value, and live clustering.
- USDC contract — good for demonstrating honest degradation when clustering data is limited or explorer sampling is partial.

## Chain coverage today

- Ethereum: strongest experience with live enrichment, live clustering, watchlists, alerts, incidents, and cases.
- Base, Arbitrum, BSC, Polygon: analyst-driven scoring and workflow support, ready for deeper live integrations later.
- Solana: manual intake plus intelligence, watchlist, alerting, incidents, and case workflows.

## Important files

- `app/page.tsx` — main signed-out and signed-in product experience.
- `app/globals.css` — shared design system, glass surfaces, onboarding, and workflow styles.
- `lib/api.ts` — browser API client for auth, intelligence, alerts, incidents, and cases.
- `lib/types.ts` — shared UI contracts for API payloads and domain types.

## Validation

Production build check:

```bash
npm run build
```

This should compile cleanly before shipping UI changes.
