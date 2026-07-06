"""
Login notification email service for InsightAI.
Sends an HTML email after every successful login.
All errors are caught and logged — email failures never block login.
"""
import html as _html
import os
import json
import re
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen
from urllib.error import URLError


# ── Input sanitization ────────────────────────────────────────────────────────

def _strip_crlf(value: str) -> str:
    """Remove CR/LF characters to prevent email-header injection."""
    return re.sub(r"[\r\n]", "", value)


def _sanitize_display(value: str, max_len: int = 200) -> str:
    """
    Sanitize a value that will be shown in email body text.
    - Strips control characters (except tab/space)
    - Truncates to max_len
    The result is still passed through html.escape() before HTML insertion.
    """
    cleaned = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", value or "")
    return cleaned[:max_len]


def _safe_ip(raw_ip: str) -> str:
    """
    Validate that the IP is a plausible IPv4/IPv6 address or return 'Unknown'.
    Prevents arbitrary strings from ip header being used as display/lookup value.
    """
    ip = (raw_ip or "").strip()
    # Allow IPv4 dotted-decimal, IPv6 hex-colon, or localhost
    if re.match(r"^[\da-fA-F:.]{1,45}$", ip):
        return ip
    return "Unknown"


# ── IP geolocation ────────────────────────────────────────────────────────────

def _get_location(ip: str) -> str:
    """Return an approximate location string for the given IP address."""
    if not ip or ip in ("127.0.0.1", "::1", "localhost", "unknown"):
        return "Local / Development"
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,city,regionName,country"
        with urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            parts = [data.get("city"), data.get("regionName"), data.get("country")]
            return ", ".join(p for p in parts if p) or "Unknown"
    except (URLError, Exception):
        pass
    return "Unknown"


# ── User-Agent parsing (no extra packages) ────────────────────────────────────

def _parse_browser_device(user_agent: str) -> str:
    """Return a human-readable 'Browser on Device' string from a UA header."""
    ua = user_agent or ""

    if "Edg/" in ua or "EdgA/" in ua:
        browser = "Microsoft Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Chrome/" in ua:
        browser = "Google Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        browser = "Unknown Browser"

    if "iPhone" in ua:
        device = "iPhone"
    elif "iPad" in ua:
        device = "iPad"
    elif "Android" in ua:
        device = "Android Device"
    elif "Windows" in ua:
        device = "Windows PC"
    elif "Macintosh" in ua or "Mac OS X" in ua:
        device = "Mac"
    elif "Linux" in ua:
        device = "Linux"
    else:
        device = "Unknown Device"

    return f"{browser} on {device}"


# ── HTML email template ───────────────────────────────────────────────────────

def _build_html(username: str, formatted_time: str, ip: str,
                browser_device: str, location: str) -> str:
    # Escape ALL dynamic values before HTML insertion to prevent injection
    e_username       = _html.escape(username,       quote=True)
    e_formatted_time = _html.escape(formatted_time, quote=True)
    e_ip             = _html.escape(ip,             quote=True)
    e_browser_device = _html.escape(browser_device, quote=True)
    e_location       = _html.escape(location,       quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Successful Login – InsightAI</title>
</head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fa;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 4px 20px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1565C0 0%,#1976D2 100%);
                        padding:36px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;
                          letter-spacing:-0.5px;">InsightAI</h1>
              <p style="margin:6px 0 0;color:#90CAF9;font-size:13px;">
                AI-Powered Decision Intelligence Platform
              </p>
            </td>
          </tr>

          <!-- Alert badge -->
          <tr>
            <td style="padding:28px 40px 0;text-align:center;">
              <span style="display:inline-block;background:#E3F2FD;color:#1565C0;
                            font-size:13px;font-weight:600;padding:6px 18px;
                            border-radius:20px;letter-spacing:0.5px;">
                ✓ &nbsp;LOGIN SUCCESSFUL
              </span>
            </td>
          </tr>

          <!-- Greeting -->
          <tr>
            <td style="padding:20px 40px 8px;">
              <h2 style="margin:0;font-size:20px;color:#212121;font-weight:600;">
                Hello, {e_username}
              </h2>
              <p style="margin:8px 0 0;color:#555;font-size:14px;line-height:1.6;">
                A successful login to your InsightAI account was detected. 
                If this was you, no action is required. If you did not perform 
                this login, please change your password immediately.
              </p>
            </td>
          </tr>

          <!-- Login details table -->
          <tr>
            <td style="padding:24px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="border:1px solid #E0E0E0;border-radius:8px;overflow:hidden;">
                <tr style="background:#F5F7FA;">
                  <td colspan="2"
                      style="padding:12px 16px;font-size:12px;font-weight:700;
                              color:#1976D2;letter-spacing:1px;text-transform:uppercase;">
                    Login Details
                  </td>
                </tr>
                <tr style="border-top:1px solid #E0E0E0;">
                  <td style="padding:12px 16px;font-size:13px;color:#757575;
                              font-weight:600;width:40%;border-right:1px solid #E0E0E0;">
                    Date &amp; Time
                  </td>
                  <td style="padding:12px 16px;font-size:13px;color:#212121;">
                    {formatted_time}
                  </td>
                </tr>
                <tr style="border-top:1px solid #E0E0E0;background:#FAFAFA;">
                  <td style="padding:12px 16px;font-size:13px;color:#757575;
                              font-weight:600;border-right:1px solid #E0E0E0;">
                    IP Address
                  </td>
                  <td style="padding:12px 16px;font-size:13px;color:#212121;">
                    {e_ip}
                  </td>
                </tr>
                <tr style="border-top:1px solid #E0E0E0;">
                  <td style="padding:12px 16px;font-size:13px;color:#757575;
                              font-weight:600;border-right:1px solid #E0E0E0;">
                    Browser / Device
                  </td>
                  <td style="padding:12px 16px;font-size:13px;color:#212121;">
                    {e_browser_device}
                  </td>
                </tr>
                <tr style="border-top:1px solid #E0E0E0;background:#FAFAFA;">
                  <td style="padding:12px 16px;font-size:13px;color:#757575;
                              font-weight:600;border-right:1px solid #E0E0E0;">
                    Approximate Location
                  </td>
                  <td style="padding:12px 16px;font-size:13px;color:#212121;">
                    {e_location}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Security tip -->
          <tr>
            <td style="padding:0 40px 28px;">
              <div style="background:#FFF8E1;border-left:4px solid #FFC107;
                           border-radius:0 6px 6px 0;padding:14px 16px;">
                <p style="margin:0;font-size:13px;color:#5D4037;line-height:1.6;">
                  <strong>Tip:</strong> InsightAI will never ask for your password 
                  via email. If you receive suspicious messages, report them 
                  immediately.
                </p>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#F5F7FA;padding:20px 40px;text-align:center;
                        border-top:1px solid #E0E0E0;">
              <p style="margin:0;font-size:12px;color:#9E9E9E;">
                This is an automated security notification from InsightAI.<br>
                Please do not reply to this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ── Plain-text fallback ───────────────────────────────────────────────────────

def _build_plain(username: str, formatted_time: str, ip: str,
                 browser_device: str, location: str) -> str:
    return (
        f"InsightAI — Successful Login Notification\n"
        f"{'=' * 44}\n\n"
        f"Hello {username},\n\n"
        f"A successful login to your InsightAI account was detected.\n\n"
        f"Login Details\n"
        f"-------------\n"
        f"Date & Time       : {formatted_time}\n"
        f"IP Address        : {ip}\n"
        f"Browser / Device  : {browser_device}\n"
        f"Approx. Location  : {location}\n\n"
        f"If this was you, no action is required.\n"
        f"If you did not perform this login, change your password immediately.\n\n"
        f"-- InsightAI Security Team\n"
    )


# ── Core send function ────────────────────────────────────────────────────────

def _send(to_email: str, username: str, ip: str, user_agent: str,
          login_time: datetime) -> None:
    """
    Resolve location, build email, and deliver via SMTP.
    All exceptions are caught so this thread never propagates.
    """
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_from = os.environ.get("SMTP_FROM", smtp_user).strip()

    if not smtp_host or not smtp_user or not smtp_pass:
        print("[InsightAI email] SMTP not configured — login notification skipped.")
        return

    # Sanitize all attacker-controlled inputs before use anywhere
    # _safe_ip validates format; _sanitize_display strips control chars; _strip_crlf
    # prevents CRLF injection in any context where the value might reach a header.
    clean_ip       = _safe_ip(ip)
    clean_ua       = _sanitize_display(user_agent, max_len=300)
    clean_username = _strip_crlf(_sanitize_display(username, max_len=100))
    clean_to       = _strip_crlf(to_email)
    clean_from     = _strip_crlf(smtp_from)

    formatted_time = login_time.strftime("%B %d, %Y at %I:%M:%S %p UTC")
    location       = _get_location(clean_ip)
    browser_device = _parse_browser_device(clean_ua)

    html  = _build_html(clean_username, formatted_time, clean_ip, browser_device, location)
    plain = _build_plain(clean_username, formatted_time, clean_ip, browser_device, location)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Successful Login to InsightAI"
    msg["From"]    = f"InsightAI Security <{clean_from}>"
    msg["To"]      = clean_to
    msg["X-Mailer"] = "InsightAI/1.0"
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))   # html last = preferred by clients

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(clean_from, [clean_to], msg.as_string())
        print(f"[InsightAI email] Login notification sent to {to_email}")
    except smtplib.SMTPAuthenticationError:
        print("[InsightAI email] SMTP authentication failed — check SMTP_USER / SMTP_PASSWORD.")
    except smtplib.SMTPConnectError:
        print(f"[InsightAI email] Could not connect to SMTP server {smtp_host}:{smtp_port}.")
    except Exception as exc:
        print(f"[InsightAI email] Unexpected send error: {exc}")


# ── Public API ────────────────────────────────────────────────────────────────

def send_login_notification(to_email: str, username: str,
                             ip_address: str, user_agent: str) -> None:
    """
    Fire-and-forget: dispatch a daemon thread to send the login email.
    Returns immediately — never blocks the HTTP response or raises.
    Only sends on successful login; callers must NOT call this on failure.
    """
    login_time = datetime.utcnow()
    t = threading.Thread(
        target=_send,
        args=(to_email, username, ip_address, user_agent, login_time),
        daemon=True,
        name="login-email",
    )
    t.start()
