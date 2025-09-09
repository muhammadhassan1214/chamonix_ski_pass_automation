import logging
from typing import Any, Dict, Optional

from mail_sender import send_error_email
import traceback

logger = logging.getLogger("process_runner")


def _get_bot_class_for_site(site: Optional[str]):
    """Lazy-resolve the bot class for a given site key.

    Supported: 'cbm' -> CBMPortalBot, 'earlybird' -> EARLYBIRDPortalBot
    Returns (BotClass, error_message). BotClass is None on failure.
    """
    if not site:
        return None, "no_site_specified"

    key = site.strip().lower()
    if key == "cbm":
        try:
            from cbm_portal import CBMPortalBot

            return CBMPortalBot, None
        except Exception as e:
            logger.exception("Failed to import CBMPortalBot: %s", e)
            return None, "cbm_import_failed"

    if key in ("earlybird", "early-bird", "early_bird"):
        try:
            from earlybird_portal import EARLYBIRDPortalBot

            return EARLYBIRDPortalBot, None
        except Exception as e:
            logger.exception("Failed to import EARLYBIRDPortalBot: %s", e)
            return None, "earlybird_import_failed"

    return None, f"unsupported_site:{key}"


def process_order_runner(order_data: Dict[str, Any]) -> Optional[str]:
    """Process an order end-to-end and return a voucher file path (or None on failure).

    Flow:
    - Determine site via order_data['site'] (default: 'cbm')
    - Lazy-import and instantiate the appropriate bot class
    - initialize_driver(), login(), process_order(order_data)
    - cleanup() always called

    Returns:
    - voucher path string on success (if bot returns it), otherwise None.
    """
    order_id = order_data.get("order_id") or order_data.get("id")
    site = order_data.get("site") or "cbm"

    bot_class, err = _get_bot_class_for_site(site)
    if not bot_class:
        logger.error("Order %s: bot selection failed: %s", order_id, err)
        return None

    bot = None
    try:
        bot = bot_class()

        # initialize driver
        init_ok = getattr(bot, "initialize_driver", lambda: True)()
        if not init_ok:
            logger.error("Order %s: driver initialization failed", order_id)
            return None

        # login
        login_ok = getattr(bot, "login", lambda: True)()
        if not login_ok:
            logger.error("Order %s: login failed", order_id)
            return None

        # process order
        result = getattr(bot, "process_order")(order_data)

        # If result is a dict and contains voucher_path, return it
        if isinstance(result, dict):
            if result.get("success") and result.get("voucher_path"):
                return result.get("voucher_path")
            # success but no voucher yet
            if result.get("success"):
                return None
            # failure
            logger.error("Order %s: processing failed: %s", order_id, result.get("error"))
            return None

        # If the bot returned a string (path), return it directly
        if isinstance(result, str):
            return result

        # Unknown result type
        logger.warning("Order %s: unexpected result type from process_order: %r", order_id, type(result))
        return None

    except Exception as e:
        logger.exception("Order %s: unexpected error: %s", order_id, e)

        # Send error email
        error_message = f"Unexpected error occurred for order {order_id}: {str(e)}"
        stack_trace = traceback.format_exc()
        send_error_email(error_message, stack_trace)

        return None

    finally:
        if bot:
            getattr(bot, "cleanup", lambda: None)()


if __name__ == "__main__":
    # simple manual test harness
    sample = {"order_id": "test-1", "site": "cbm"}
    print(process_order_runner(sample))
