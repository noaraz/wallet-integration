# wallet-integration

Personal Telegram bot that turns ticket screenshots into Google Wallet passes.

**Pipeline:** Telegram photo → Claude Vision extracts ticket fields → Python lib decodes QR/barcode → signed JWT for Google Wallet `eventTicketObject` → bot replies with an "Add to Google Wallet" link.

See [PLAN.md](PLAN.md) for the roadmap, [STATUS.md](STATUS.md) for current state, and [CLAUDE.md](CLAUDE.md) for architecture and conventions.
