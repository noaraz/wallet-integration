---
name: wallet-jwt-validator
description: Given a built Google Wallet JWT (the `<jwt>` portion of a `pay.google.com/gp/v/save/<jwt>` URL), decodes the header + payload, validates required claims and issuer identity, and optionally dry-runs an `eventTicketObject.insert` against the Wallet API test environment. Use during Phase 04 and onward whenever a wallet-pass builder changes.
---

You validate a Google Wallet `eventTicketObject` JWT and (optionally) its corresponding REST upsert.

## Inputs

- The JWT string (three base64url-encoded sections separated by `.`).
- Optional: the `eventTicketClass` ID the object references.

## Validation steps

1. **Header**
   - `alg` must be `RS256`.
   - `typ` must be `JWT` (absent is also acceptable).

2. **Payload top-level claims**
   - `iss` — service account email, matches the env-configured issuer.
   - `aud` — must be `google`.
   - `typ` — must be `savetowallet`.
   - `iat` — present and within ±5 minutes of now.
   - `origins` — list of origins the save URL can be called from.
   - `payload.eventTicketObjects` (or `eventTicketClasses`) — non-empty.

3. **Each eventTicketObject**
   - `id` format: `<issuerId>.<uniqueSuffix>`.
   - `classId` matches an existing class (if the class ID was provided, compare).
   - `state` is `ACTIVE` (or intentionally other).
   - `barcode` present with `type` ∈ {`QR_CODE`, `CODE_128`, `AZTEC`, `PDF_417`}; `value` non-empty.
   - `ticketHolderName`, `eventName`, `venue`, `dateTime` — present or explicitly omitted with a reason.

4. **Signature** (optional if private key available)
   - Decode the service-account public key from the JSON key, verify RS256 signature.

5. **Dry-run REST call** (optional, requires staging credentials)
   - `POST https://walletobjects.googleapis.com/walletobjects/v1/eventTicketObject` with the object body.
   - Report the status code and the full error body on failure.

## Output format

```
## Wallet JWT validation

### Header
- alg: RS256 ✅
- typ: JWT ✅

### Claims
- iss: <service-account> ✅
- aud: google ✅
- iat: <iso> (Δ=<seconds>) ✅

### Object(s)
- <classId>.<objectId>
  - barcode: QR_CODE ✅
  - required fields: all present ✅

### REST dry-run (if executed)
- status: 200 ✅ (or the error body)

### Save URL
- https://pay.google.com/gp/v/save/<jwt>
```

Flag any failure clearly and do not proceed to "Save URL" if validation didn't pass.
