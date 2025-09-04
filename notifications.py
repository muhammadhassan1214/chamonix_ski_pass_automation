import os
import logging
import requests
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def send_slack_alert(message: str, webhook_url: Optional[str] = None) -> bool:
    """Send alert to Slack channel."""
    try:
        if not webhook_url:
            webhook_url = os.getenv('SLACK_WEBHOOK_URL')

        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        payload = {
            'text': f"🎿 Chamonix Ski Pass Automation Alert",
            'attachments': [
                {
                    'color': 'danger',
                    'fields': [
                        {
                            'title': 'Alert',
                            'value': message,
                            'short': False
                        },
                        {
                            'title': 'Timestamp',
                            'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'short': True
                        }
                    ]
                }
            ]
        }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info(f"Slack alert sent successfully: {message}")
            return True
        else:
            logger.error(f"Failed to send Slack alert: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending Slack alert: {e}")
        return False

def send_email_alert(subject: str, message: str, recipient: Optional[str] = None) -> bool:
    """Send email alert."""
    try:
        if not recipient:
            recipient = os.getenv('ALERT_EMAIL')

        if not recipient:
            logger.warning("Alert email recipient not configured")
            return False

        # For now, just log the email
        logger.info(f"EMAIL ALERT - To: {recipient}, Subject: {subject}, Message: {message}")
        return True

    except Exception as e:
        logger.error(f"Error sending email alert: {e}")
        return False

def send_order_completion_notification(order_id: int, voucher_path: str) -> bool:
    """Send notification when order is completed."""
    try:
        message = f"Order {order_id} completed successfully. Voucher saved: {voucher_path}"

        # Send to Slack
        slack_sent = send_slack_alert(message)

        # Could also trigger WooCommerce email here
        logger.info(f"Order completion notification sent for order {order_id}")

        return slack_sent

    except Exception as e:
        logger.error(f"Error sending completion notification: {e}")
        return False
