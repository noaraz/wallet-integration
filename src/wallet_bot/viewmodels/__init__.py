"""ViewModels — one orchestrator per telegram interaction.

Take raw (already-parsed) telegram input, call services, and return a
view-model object that a view can render. Must be unit-testable with only
fake services — no Telegram instance required.

Planned modules:
    start_viewmodel   (Phase 1)
    help_viewmodel    (Phase 1)
    photo_viewmodel   (Phase 5) — the main pipeline
"""
