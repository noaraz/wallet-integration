# Phase 04 — notes

## Open design questions (to resolve during brainstorming)

### Multiple tickets for the same event

When a user buys several seats to the same event and sends multiple ticket photos:

- **Class vs object split**: one `eventTicketClass` per event, one `eventTicketObject` per ticket. The class holds event metadata (name, venue, date); each object holds the seat/barcode.
- **UX for sending**: do we handle one photo per message (simplest), or support an album (multiple photos in one Telegram message)?
- **Deduplication**: if the same ticket photo is sent twice, detect the duplicate barcode and skip creating a second pass rather than adding a duplicate to the wallet.
- **Save link**: Google Wallet supports a batch save URL that adds multiple objects in one tap — prefer this over sending N separate links when multiple tickets are detected for the same event.
