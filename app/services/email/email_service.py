import logging
from typing import List, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        self.smtp_server = settings.MAIL_SERVER
        self.smtp_port = settings.MAIL_PORT
        self.username = settings.MAIL_USERNAME
        self.password = settings.MAIL_PASSWORD
        self.from_email = settings.MAIL_FROM
        self.from_name = settings.MAIL_FROM_NAME
        
        # Setup Jinja2 for email templates
        self.template_env = Environment(
            loader=FileSystemLoader('app/templates/email')
        )
    
    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str,
        text_content: str = None
    ) -> bool:
        """Send email"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text part
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email to new user"""
        try:
            template = self.template_env.get_template('welcome.html')
            html_content = template.render(
                username=username,
                app_name="AI Retail Management System"
            )
            
            return await self.send_email(
                to_email=to_email,
                subject="Welcome to AI Retail Management System",
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self, 
        to_email: str, 
        username: str, 
        reset_token: str
    ) -> bool:
        """Send password reset email"""
        try:
            reset_url = f"http://localhost:3000/reset-password?token={reset_token}"
            
            template = self.template_env.get_template('password_reset.html')
            html_content = template.render(
                username=username,
                reset_url=reset_url,
                app_name="AI Retail Management System"
            )
            
            return await self.send_email(
                to_email=to_email,
                subject="Password Reset Request",
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return False