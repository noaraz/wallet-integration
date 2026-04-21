"""Views — format telegram replies (text, inline keyboards).

Pure functions of viewmodel output. Views should NEVER call services or
perform I/O — they only shape data for the Telegram response payload.

Planned modules:
    start_view   (Phase 1)
    help_view    (Phase 1)
    photo_view   (Phase 5) — renders the "Add to Google Wallet" button
"""
