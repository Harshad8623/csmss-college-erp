import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def send_otp_email(to_email, otp_code, user_name):
    """
    Sends a 6-digit OTP email using smtplib.
    Returns True if sent successfully, False otherwise.
    """
    smtp_server = current_app.config.get('MAIL_SERVER')
    smtp_port = current_app.config.get('MAIL_PORT')
    smtp_user = current_app.config.get('MAIL_USERNAME')
    smtp_pass = current_app.config.get('MAIL_PASSWORD')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or smtp_user
    college_name = current_app.config.get('COLLEGE_NAME', 'CSMSS College')

    if not smtp_server or not smtp_user or not smtp_pass:
        logger.error("SMTP configuration is missing. Cannot send OTP.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{college_name} - Password Reset OTP"
    msg['From'] = f"{college_name} ERP <{sender}>"
    msg['To'] = to_email

    # Plain text fallback
    text = f"""
    Hello {user_name},
    
    You have requested to reset your password.
    Your 6-digit OTP code is: {otp_code}
    
    This code will expire in 10 minutes.
    If you did not request this, please ignore this email.
    
    Regards,
    {college_name} Admin
    """

    # HTML Version with glassmorphism-inspired simple styling
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
          <h2 style="color: #2c3e50; text-align: center; margin-bottom: 30px;">Password Reset</h2>
          <p style="color: #555; font-size: 16px;">Hello {user_name},</p>
          <p style="color: #555; font-size: 16px;">We received a request to reset your password. Here is your One-Time Password (OTP):</p>
          
          <div style="text-align: center; margin: 30px 0;">
            <span style="display: inline-block; padding: 15px 30px; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #007bff; background: #f0f8ff; border: 2px dashed #007bff; border-radius: 8px;">
              {otp_code}
            </span>
          </div>
          
          <p style="color: #555; font-size: 16px;">This code is valid for <strong>10 minutes</strong>.</p>
          <p style="color: #777; font-size: 14px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
            If you did not request a password reset, please safely ignore this email. Your account remains secure.
          </p>
          <p style="color: #999; font-size: 12px; text-align: center; margin-top: 20px;">
            &copy; {college_name} ERP System
          </p>
        </div>
      </body>
    </html>
    """

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    msg.attach(part1)
    msg.attach(part2)

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, to_email, msg.as_string())
            server.quit()
        else:
            # SSL
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, to_email, msg.as_string())
            server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False
