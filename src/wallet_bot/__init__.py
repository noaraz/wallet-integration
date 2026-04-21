"""wallet-bot — Telegram → Google Wallet pass bot.

See CLAUDE.md for architecture. MVVM layout:
    models/      pure domain data
    services/    external integrations
    viewmodels/  orchestrators per telegram interaction
    views/       telegram reply formatting
"""

__version__ = "0.0.0"
