import os
import time
import logging
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from utils import (
    get_undetected_driver, safe_navigate_to_url, input_element,
    click_element_by_js, wait_for_page_load, select_by_text,
    check_element_exists, get_element_text, handle_pop_up
)
from dotenv import load_dotenv
from mail_sender import send_error_email
import traceback

load_dotenv()

logger = logging.getLogger(__name__)

class EARLYBIRDPortalBot:
    def __init__(self):
        self.driver = None
        self.base_url = "https://partenaire.montblancnaturalresort.ski/offre-earlybooking/"
        self.username = os.getenv('EARLYBIRD_USERNAME')
        self.password = os.getenv('EARLYBIRD_PASSWORD')

        if not self.username or not self.password:
            raise ValueError("EARLYBIRD credentials not found in environment variables")

    def initialize_driver(self) -> bool:
        """Initialize the Chrome driver."""
        try:
            if self.driver:
                self.cleanup()

            self.driver = get_undetected_driver(headless=False)
            if not self.driver:
                logger.error("Failed to initialize Chrome driver")
                return False

            logger.info("Chrome driver initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing driver: {e}")
            return False

    def login(self) -> bool:
        """Log in to the CBM portal."""
        try:
            safe_navigate_to_url(self.driver, self.base_url)
            wait_for_page_load(self.driver)
            time.sleep(5)  # wait for potential redirects
            already_logged_in = check_element_exists(self.driver, (By.XPATH, "//h1[contains(text(), 'EB – AD & Co')]"))
            if already_logged_in:
                logger.info("Already logged in")
                return True
            # Find and fill the username and password fields
            handle_pop_up(self.driver, (By.ID, "tarteaucitronPersonalize2"))
            input_element(self.driver, (By.ID, "mat-input-0"), self.username)
            click_element_by_js(self.driver, (By.XPATH, f"//span[contains(text(), '{self.username}')]"))
            input_element(self.driver, (By.ID, "password"), self.password)

            # Click the login button
            click_element_by_js(self.driver, (By.XPATH, "//button[contains(text(), 'Connexion')]"))

            # Wait for navigation after login
            wait_for_page_load(self.driver)

            logger.info("Login successful")
            return True

        except Exception as e:
            logger.error(f"Error during login: {e}")

            # Send error email
            error_message = f"Error during login: {str(e)}"
            stack_trace = traceback.format_exc()
            send_error_email(error_message, stack_trace)

            return False

    def process_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main method to process an order."""
        try:
            # For now, return a mock successful result
            # TODO: Implement actual portal automation
            logger.info(f"Mock processing order: {order_data.get('order_id')}")

            # Simulate processing time
            time.sleep(2)

            return {
                'success': True,
                'voucher_path': f"/mock/vouchers/order_{order_data.get('order_id')}.pdf",
                'portal': 'CBM'
            }

        except Exception as e:
            logger.error(f"Error processing order: {e}")

            # Send error email
            error_message = f"Error processing order: {str(e)}"
            stack_trace = traceback.format_exc()
            send_error_email(error_message, stack_trace)

            return {'success': False, 'error': str(e)}

    def cleanup(self):
        """Clean up resources."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
