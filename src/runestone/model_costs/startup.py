"""Best-effort startup maintenance for the local model-price registry."""

import logging

from runestone.config import Settings
from runestone.model_costs.pricing import refresh_price_snapshot

logger = logging.getLogger(__name__)


async def refresh_startup_model_prices(app_settings: Settings) -> None:
    """Refresh pricing without allowing source failures to affect readiness."""
    try:
        counts = await refresh_price_snapshot(app_settings)
    except Exception:
        logger.exception("Startup model price refresh failed; existing prices remain active")
        return

    logger.info(
        "Startup model price refresh completed models.dev=%d portkey=%d stale=%d manual=%d unknown=%d",
        counts.models_dev,
        counts.portkey,
        counts.stale,
        counts.manual,
        counts.unknown,
    )
