import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def send_error_email(error_message, stack_trace):
    """
    Sends an error email with the provided error details using Postmark SMTP.

    Args:
        error_message (str): The error message to include in the email.
        stack_trace (str): The stack trace to include in the email.
    """
    # Load Postmark configuration from environment variables
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT"))
    api_key = os.getenv("POSTMARK_API_KEY")
    smtp_from = os.getenv("SMTP_FROM")
    smtp_to = os.getenv("SMTP_TO")
    message_stream = os.getenv("POSTMARK_MESSAGE_STREAM", "outbound")  # Default to 'outbound'

    # Create the email content
    subject = "Automation Error Notification"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    body = f"""
    <html>
    <body>
        <h2 style='color: red;'>Automation Error Notification</h2>
        <p><strong>Timestamp:</strong> {timestamp}</p>
        <p><strong>Error Message:</strong></p>
        <pre>{error_message}</pre>
        <p><strong>Stack Trace:</strong></p>
        <pre>{stack_trace}</pre>
    </body>
    </html>
    """

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = smtp_to
    msg['Subject'] = subject
    msg['X-PM-MESSAGE-STREAM'] = message_stream  # Add the Postmark message stream header

    # Attach the HTML body
    msg.attach(MIMEText(body, 'html'))

    try:
        # Connect to the Postmark SMTP server and send the email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(api_key, api_key)  # Postmark uses the API key as both username and password
            server.sendmail(smtp_from, smtp_to, msg.as_string())
        print("Error email sent successfully.")
    except Exception as e:
        print(f"Failed to send error email: {e}")
