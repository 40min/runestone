"""Best-effort startup maintenance for the local model-price registry."""

import logging
import time

from runestone.config import Settings
from runestone.core.error_tracking import capture_sanitized_exception, duration_bucket
from runestone.model_costs.pricing import refresh_price_snapshot

logger = logging.getLogger(__name__)


async def refresh_startup_model_prices(app_settings: Settings) -> None:
    """Refresh pricing without allowing source failures to affect readiness."""
    started_at = time.monotonic()
    try:
        counts = await refresh_price_snapshot(app_settings)
    except Exception as exception:
        logger.error(
            "Startup model price refresh failed; existing prices remain active",
            exc_info=True,
            extra={
                "runestone_telemetry": {
                    "operation": "model_price_refresh",
                    "outcome": "failed",
                    "duration_bucket": duration_bucket(started_at),
                }
            },
        )
        capture_sanitized_exception(exception)
        return

    logger.info(
        "Startup model price refresh completed models.dev=%d portkey=%d stale=%d manual=%d unknown=%d",
        counts.models_dev,
        counts.portkey,
        counts.stale,
        counts.manual,
        counts.unknown,
    )
