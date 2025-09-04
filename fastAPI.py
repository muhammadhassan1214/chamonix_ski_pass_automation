from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import hmac
import hashlib
import base64
import json
import os
import uvicorn
import logging
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv

load_dotenv()


# --- App and logging setup ---
app = FastAPI(title="Chamonix Ski Pass Automation - Webhook Listener")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("fastapi_webhook")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
logger.setLevel(LOG_LEVEL)


# Shared secret (preferred from env)
SHARED_SECRET = os.getenv("WEBHOOK_SECRET") or os.getenv("SHARED_SECRET") or "CspaAOH15wwWrai"


class WebhookPayload(BaseModel):
    id: Optional[int] = None
    order_id: Optional[int] = None
    status: Optional[str] = Field(None, description="Order status, e.g. processing")
    line_items: Optional[List[Dict[str, Any]]] = None
    billing: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


def verify_signature_base64(request_body: bytes, signature: str) -> bool:
    """Verify WooCommerce webhook signature which is base64(hmac_sha256(payload, secret)).

    Returns True when signature matches. Handles empty secret by allowing through (configurable).
    """
    try:
        if not SHARED_SECRET:
            logger.warning("No webhook secret configured; skipping signature verification")
            return True

        expected = base64.b64encode(
            hmac.new(SHARED_SECRET.encode("utf-8"), request_body, hashlib.sha256).digest()
        ).decode()

        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.exception("Error verifying signature")
        return False


def run_automation(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for the real automation entrypoint.

    Should be replaced with your Selenium/Playwright logic. Returns a result dict.
    Keep this function robust and exception-safe.
    """
    logger.info("Starting automation for order: %s", order_data.get("order_id") or order_data.get("id"))
    try:
        # Lazy import to avoid startup dependency cycles
        from process_runner import process_order_runner

        logger.debug("Calling process_runner for payload: %s", json.dumps(order_data))
        result = process_order_runner(order_data)
        return result
    except Exception:
        logger.exception("Automation failed for order: %s", order_data.get("order_id"))
        return {"success": False, "error": "automation_exception"}


async def _process_order_background(order_data: Dict[str, Any]):
    """Background worker wrapper: runs automation and handles/reporting errors."""
    try:
        result = run_automation(order_data)
        if not result.get("success"):
            # Import notifications lazily to avoid startup cost if not configured
            try:
                from notifications import send_slack_alert
                send_slack_alert(f"Order {order_data.get('order_id')} failed: {result.get('error') or result.get('message')}")
            except Exception:
                logger.exception("Failed to send failure notification")

        logger.info("Background processing finished for order %s: %s", order_data.get("order_id"), result)
    except Exception:
        logger.exception("Unhandled exception in background processing for order %s", order_data.get("order_id"))
        try:
            from notifications import send_slack_alert
            send_slack_alert(f"Critical error processing order {order_data.get('order_id')}")
        except Exception:
            logger.exception("Failed to send critical error notification")


@app.post("/webhook/woocommerce")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive WooCommerce webhook, verify signature, enqueue background automation."""
    raw_body = b""
    try:
        raw_body = await request.body()
        # WooCommerce sometimes uses header 'X-WC-Webhook-Signature' or lowercase
        signature = request.headers.get("X-WC-Webhook-Signature") or request.headers.get("x-wc-webhook-signature") or ""

        if signature:
            if not verify_signature_base64(raw_body, signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

        # Parse JSON safely
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

        # Validate with Pydantic model (keeps flexibility)
        webhook = WebhookPayload.parse_obj(payload)

        order_id = webhook.id or webhook.order_id or payload.get("order_id") or payload.get("id")
        status_value = (webhook.status or payload.get("status") or "").lower()

        logger.info("Received webhook for order %s with status '%s'", order_id, status_value)

        # Only process orders that become 'processing'
        if status_value != "processing":
            logger.info("Ignoring order %s with status '%s'", order_id, status_value)
            return JSONResponse(status_code=200, content={"message": f"Order {order_id} status {status_value} - not processing"})

        # Enqueue background processing
        background_tasks.add_task(_process_order_background, payload)

        return JSONResponse(status_code=202, content={"status": "accepted", "order_id": order_id})

    except HTTPException:
        # re-raise FastAPI HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Unexpected error handling webhook")
        # Avoid returning internal error details
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/webhook/test-manual")
async def dev_manual_webhook(request: Request, background_tasks: BackgroundTasks):
    """Development-only endpoint to POST a JSON payload and trigger the automation without signature.

    Enable by setting environment variable DEV_WEBHOOK_ENABLED to '1' or 'true'. This is intentionally
    gated to avoid accidental exposure in production.
    """
    enabled = os.getenv("DEV_WEBHOOK_ENABLED", "false").lower() in ("1", "true", "yes")
    if not enabled:
        logger.warning("Dev webhook called but DEV_WEBHOOK_ENABLED is disabled")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev webhook disabled")

    try:
        payload = await request.json()
    except Exception:
        logger.exception("Invalid JSON on dev webhook")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload must be a JSON object")

    order_id = payload.get("order_id") or payload.get("id")
    logger.info("Dev manual webhook received for order %s", order_id)

    # Enqueue background processing without signature check
    background_tasks.add_task(_process_order_background, payload)

    return JSONResponse(status_code=202, content={"status": "accepted", "order_id": order_id})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTPException: %s %s", exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "internal_server_error"})


if __name__ == "__main__":
    # Run uvicorn only when executed directly
    uvicorn.run("fastAPI:app", host="0.0.0.0", port=int(os.getenv("PORT", 5000)), reload=False)
