import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


def send_otp_email(to_email, otp_code, user_name):
    """
    Sends a 6-digit OTP email.
    Strategy:
      1. If BREVO_API_KEY is set → use Brevo HTTP API (works on Render free tier)
      2. Otherwise → fall back to SMTP (works locally)
    Returns True if sent, False on failure.
    """
    brevo_key = current_app.config.get('BREVO_API_KEY', '')
    if brevo_key:
        return _send_via_brevo(to_email, otp_code, user_name, brevo_key)
    else:
        return _send_via_smtp(to_email, otp_code, user_name)


# ── Brevo (Sendinblue) HTTP API ───────────────────────────────────────────────
def _send_via_brevo(to_email, otp_code, user_name, api_key):
    """Send using Brevo REST API — works on Render free tier (HTTPS, not SMTP)."""
    try:
        import urllib.request
        import urllib.error
        import json

        cfg          = current_app.config
        sender_email = cfg.get('MAIL_USERNAME', 'noreply@college.edu')
        college_name = cfg.get('COLLEGE_NAME', 'CSMSS College')

        html_body = _build_html(otp_code, user_name, college_name)
        text_body = _build_text(otp_code, user_name, college_name)

        payload = json.dumps({
            "sender":      {"name": f"{college_name} ERP", "email": sender_email},
            "to":          [{"email": to_email, "name": user_name}],
            "subject":     f"{college_name} - Password Reset OTP",
            "htmlContent": html_body,
            "textContent": text_body,
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "accept":       "application/json",
                "content-type": "application/json",
                "api-key":      api_key,
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                logger.info(f"[Brevo] OTP email sent to {to_email}")
                return True
            else:
                logger.error(f"[Brevo] Unexpected status {resp.status}")
                return False

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        logger.error(f"[Brevo] HTTP {e.code}: {body}")
        return False
    except Exception as e:
        logger.error(f"[Brevo] Failed to send OTP: {e}")
        return False


# ── SMTP fallback (localhost / paid Render plans) ─────────────────────────────
def _send_via_smtp(to_email, otp_code, user_name):
    """Send using SMTP — works locally and on paid Render plans."""
    cfg         = current_app.config
    smtp_server = cfg.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port   = cfg.get('MAIL_PORT', 587)
    smtp_user   = cfg.get('MAIL_USERNAME', '')
    smtp_pass   = cfg.get('MAIL_PASSWORD', '')
    use_tls     = cfg.get('MAIL_USE_TLS', True)
    sender      = cfg.get('MAIL_DEFAULT_SENDER') or smtp_user
    college_name = cfg.get('COLLEGE_NAME', 'CSMSS College')

    if not smtp_server or not smtp_user or not smtp_pass:
        logger.error("[SMTP] Configuration missing. Cannot send OTP.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{college_name} - Password Reset OTP"
    msg['From']    = f"{college_name} ERP <{sender}>"
    msg['To']      = to_email
    msg.attach(MIMEText(_build_text(otp_code, user_name, college_name), 'plain'))
    msg.attach(MIMEText(_build_html(otp_code, user_name, college_name), 'html'))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)

        server.login(smtp_user, smtp_pass)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        logger.info(f"[SMTP] OTP email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[SMTP] Failed to send OTP: {e}")
        return False


# ── Email content builders ────────────────────────────────────────────────────
def _build_text(otp_code, user_name, college_name):
    return f"""Hello {user_name},

Your password reset OTP code is: {otp_code}

This code expires in 10 minutes.
If you did not request this, please ignore this email.

Regards,
{college_name} ERP
"""


def _build_html(otp_code, user_name, college_name):
    return f"""<html>
  <body style="font-family:Arial,sans-serif;background:#f4f7f6;padding:20px;margin:0;">
    <div style="max-width:500px;margin:0 auto;background:#fff;padding:30px;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.08);">
      <h2 style="color:#1a56db;text-align:center;margin-bottom:24px;">Password Reset</h2>
      <p style="color:#444;font-size:15px;">Hello <strong>{user_name}</strong>,</p>
      <p style="color:#444;font-size:15px;">We received a request to reset your password. Use the OTP below:</p>
      <div style="text-align:center;margin:28px 0;">
        <span style="display:inline-block;padding:16px 32px;font-size:34px;font-weight:bold;
                     letter-spacing:8px;color:#1a56db;background:#eff6ff;
                     border:2px dashed #1a56db;border-radius:10px;">
          {otp_code}
        </span>
      </div>
      <p style="color:#555;font-size:14px;">This code is valid for <strong>10 minutes</strong>.</p>
      <p style="color:#888;font-size:13px;border-top:1px solid #eee;padding-top:16px;margin-top:24px;">
        If you did not request a password reset, you can safely ignore this email.
      </p>
      <p style="color:#aaa;font-size:12px;text-align:center;">&copy; {college_name} ERP System</p>
    </div>
  </body>
</html>"""
