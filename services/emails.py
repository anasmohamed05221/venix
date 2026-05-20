import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        """Send an HTML email via SMTP. Skipped in test environment."""
        # Skip email sending in test environment
        if settings.ENV == "testing":
            logger.info(
                "[TEST MODE] Email skipped",
                extra={"recipient": to_email, "subject": subject}
            )
            return
        
        # Log email attempt
        logger.debug(
            "Attempting to send email",
            extra={"recipient": to_email, "subject": subject}
        )

        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.MAIL_FROM
        message["To"] = to_email

        # HTML email body
        html = body
        
        # Attach HTML to message
        message.attach(MIMEText(html, "html"))

        # Send email via SMTP

        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            server.starttls()  # Upgrade to secure connection
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_FROM, to_email, message.as_string())

        # Log success
        logger.info(
            "Email sent successfully",
            extra={"recipient": to_email, "subject": subject}
        )