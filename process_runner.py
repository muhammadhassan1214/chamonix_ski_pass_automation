import logging
import time
from typing import Any, Dict, Optional

from cbm_portal import CBMPortalBot
from notifications import send_slack_alert, send_email_alert

logger = logging.getLogger("process_runner")


def process_order_runner(order_data: Dict[str, Any], max_attempts: int = 2, delay_between_attempts: int = 3) -> Dict[str, Any]:
    """Run the full order automation using CBMPortalBot with retries and notifications.

    Returns a dict with at least `success` key.
    """
    order_id = order_data.get("order_id") or order_data.get("id")

    last_error: Optional[str] = None
    for attempt in range(1, max_attempts + 1):
        bot: Optional[CBMPortalBot] = None
        try:
            logger.info("Process runner attempt %d for order %s", attempt, order_id)

            bot = CBMPortalBot()

            if not bot.initialize_driver():
                last_error = "driver_init_failed"
                logger.error("Driver initialization failed for order %s", order_id)
                raise RuntimeError(last_error)

            if not bot.login():
                last_error = "login_failed"
                logger.error("Login failed for order %s", order_id)
                raise RuntimeError(last_error)

            # Process the order using the portal bot
            result = bot.process_order(order_data)

            if result.get("success"):
                logger.info("Order %s processed successfully", order_id)
                return result

            # Non-success result -> notify and may retry
            last_error = result.get("error") or "unknown_error"
            logger.warning("Order %s processing returned non-success: %s", order_id, last_error)
            # Send a notification about failure
            try:
                send_slack_alert(f"Order {order_id} processing failed: {last_error}")
            except Exception:
                logger.exception("Failed to send slack alert for order %s", order_id)

            # decide whether to retry
            if attempt < max_attempts:
                time.sleep(delay_between_attempts)
                continue

            return {"success": False, "error": last_error}

        except Exception as e:
            last_error = str(e)
            logger.exception("Exception while processing order %s on attempt %d: %s", order_id, attempt, e)

            # Notify on exception
            try:
                send_slack_alert(f"Critical error processing order {order_id}: {last_error}")
            except Exception:
                logger.exception("Failed to send critical slack alert for order %s", order_id)

            if attempt < max_attempts:
                time.sleep(delay_between_attempts)
                continue

            return {"success": False, "error": last_error}

        finally:
            # Always try to cleanup the bot/browser
            if bot:
                try:
                    bot.cleanup()
                except Exception:
                    logger.exception("Error cleaning up bot for order %s", order_id)

    # Fallback
    return {"success": False, "error": last_error or "max_attempts_exceeded"}
