"""
Email Service for HR Platform
Handles email notifications via SMTP with graceful fallback
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending notifications."""

    def __init__(self):
        """Initialize email service with SMTP configuration from environment."""
        self.smtp_host = os.getenv('SMTP_HOST', '').strip()
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '').strip()
        self.smtp_password = os.getenv('SMTP_PASSWORD', '').strip()
        self.from_email = os.getenv('SMTP_FROM_EMAIL', '').strip()
        self.smtp_enabled = bool(self.smtp_host and self.smtp_user)

        if not self.smtp_enabled:
            logger.warning(
                "⚠️  SMTP not configured. Email notifications will be logged instead. "
                "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM_EMAIL env vars."
            )

    def is_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return self.smtp_enabled

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """Send an email via SMTP with fallback to logging.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Optional plain text fallback

        Returns:
            True if sent successfully, False otherwise
        """
        if not to_email:
            logger.error("Cannot send email: no recipient address provided")
            return False

        if not self.smtp_enabled:
            # Fallback: log the email instead
            logger.info(
                f"📧 [EMAIL NOT SENT - LOGGING ONLY]\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n"
                f"Body:\n{text_body or html_body}"
            )
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email

            # Attach plain text and HTML
            if text_body:
                msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✅ Email sent to {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending email: {e}")
            return False

    def send_leave_notification(
        self,
        to_email: str,
        employee_name: str,
        leave_type: str,
        start_date: str,
        end_date: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """Send a leave request notification email.

        Args:
            to_email: Recipient email
            employee_name: Name of the employee
            leave_type: Type of leave (vacation, sick, personal, etc.)
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            status: Status of the request (approved, rejected, pending)
            notes: Optional notes/reason

        Returns:
            True if sent, False otherwise
        """
        status_color = {
            'approved': '#27AE60',
            'rejected': '#E74C3C',
            'pending': '#F39C12'
        }.get(status.lower(), '#3498DB')

        status_text = status.upper()

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                    <h2 style="color: #1B3A5C; margin-bottom: 20px;">Leave Request Notification</h2>
                    
                    <div style="background: #f9f9f9; padding: 16px; border-radius: 6px; margin-bottom: 20px;">
                        <p><strong>Employee:</strong> {employee_name}</p>
                        <p><strong>Leave Type:</strong> {leave_type}</p>
                        <p><strong>Start Date:</strong> {start_date}</p>
                        <p><strong>End Date:</strong> {end_date}</p>
                    </div>

                    <div style="margin-bottom: 20px;">
                        <p><strong>Status:</strong></p>
                        <div style="background: {status_color}; color: white; padding: 10px 16px; border-radius: 6px; text-align: center; font-weight: bold;">
                            {status_text}
                        </div>
                    </div>

                    {f'<div style="background: #f0f0f0; padding: 12px; border-left: 4px solid #999; margin-bottom: 20px;"><strong>Notes:</strong> {notes}</div>' if notes else ''}

                    <p style="color: #666; font-size: 12px; margin-top: 20px; border-top: 1px solid #eee; padding-top: 12px;">
                        This is an automated notification from the HR Intelligence Platform.
                    </p>
                </div>
            </body>
        </html>
        """

        text_body = f"""
Leave Request Notification

Employee: {employee_name}
Leave Type: {leave_type}
Start Date: {start_date}
End Date: {end_date}
Status: {status_text}

{f'Notes: {notes}' if notes else ''}

---
This is an automated notification from the HR Intelligence Platform.
        """

        subject = f"Leave Request {status_text}: {employee_name} - {leave_type}"
        return self.send_email(to_email, subject, html_body, text_body)

    def send_approval_notification(
        self,
        to_email: str,
        request_type: str,
        requester_name: str,
        approved: bool,
        reason: Optional[str] = None
    ) -> bool:
        """Send a general approval/rejection notification.

        Args:
            to_email: Recipient email
            request_type: Type of request (leave, document, etc.)
            requester_name: Name of person who made the request
            approved: Whether request was approved
            reason: Optional reason for decision

        Returns:
            True if sent, False otherwise
        """
        status = "APPROVED" if approved else "REJECTED"
        status_color = "#27AE60" if approved else "#E74C3C"

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                    <h2 style="color: #1B3A5C; margin-bottom: 20px;">Request {status}</h2>
                    
                    <div style="background: #f9f9f9; padding: 16px; border-radius: 6px; margin-bottom: 20px;">
                        <p><strong>Request Type:</strong> {request_type}</p>
                        <p><strong>Requester:</strong> {requester_name}</p>
                    </div>

                    <div style="margin-bottom: 20px;">
                        <div style="background: {status_color}; color: white; padding: 10px 16px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 16px;">
                            {status}
                        </div>
                    </div>

                    {f'<div style="background: #f0f0f0; padding: 12px; border-left: 4px solid #999; margin-bottom: 20px;"><strong>Reason:</strong> {reason}</div>' if reason else ''}

                    <p style="color: #666; font-size: 12px; margin-top: 20px; border-top: 1px solid #eee; padding-top: 12px;">
                        For more details, log in to the HR Intelligence Platform.
                    </p>
                </div>
            </body>
        </html>
        """

        text_body = f"""
Request {status}

Request Type: {request_type}
Requester: {requester_name}
Decision: {status}

{f'Reason: {reason}' if reason else ''}

---
For more details, log in to the HR Intelligence Platform.
        """

        subject = f"{request_type} Request {status}: {requester_name}"
        return self.send_email(to_email, subject, html_body, text_body)


# Singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
