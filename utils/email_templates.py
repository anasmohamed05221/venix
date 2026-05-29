_BASE_STYLES = """
  body { margin:0; padding:0; background-color:#fafafa; font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif; }
"""


def _wrap(content: str, header_color: str = "#0a0a0a") -> str:
    return f"""
    <html>
    <head>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
      <style>{_BASE_STYLES}</style>
    </head>
    <body style="margin:0;padding:0;background-color:#fafafa;font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#fafafa;padding:48px 0;">
        <tr>
          <td align="center">
            <table width="560" cellpadding="0" cellspacing="0"
                   style="background-color:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #d4d4d8;">

              <!-- Header -->
              <tr>
                <td style="background-color:{header_color};padding:32px 40px;text-align:center;">
                  <h1 style="margin:0;color:#ffffff;font-size:18px;font-weight:700;letter-spacing:4px;text-transform:uppercase;">
                    Venix
                  </h1>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px;">
                  {content}
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background-color:#fafafa;padding:20px 40px;border-top:1px solid #d4d4d8;text-align:center;">
                  <p style="margin:0;color:#71717a;font-size:12px;">
                    This is an automated message &mdash; please do not reply.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def _button(label: str, url: str, color: str = "#0a0a0a") -> str:
    return f"""
    <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
      <tr>
        <td style="border-radius:999px;background-color:{color};">
          <a href="{url}"
             style="display:inline-block;padding:14px 36px;color:#ffffff;text-decoration:none;
                    font-size:14px;font-weight:600;border-radius:999px;letter-spacing:0.3px;">
            {label}
          </a>
        </td>
      </tr>
    </table>
    """


def _info_box(text: str, border_color: str = "#d4d4d8", bg_color: str = "#fafafa", text_color: str = "#3f3f46") -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="background-color:{bg_color};border-left:3px solid {border_color};
                   border-radius:4px;padding:14px 16px;">
          <p style="margin:0;color:{text_color};font-size:13px;line-height:1.6;">{text}</p>
        </td>
      </tr>
    </table>
    """


def verification_email(code: str) -> str:
    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Verify your email</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        Welcome to Venix. Use the code below to verify your email address.
        It expires in <strong style="color:#0a0a0a;">10 minutes</strong>.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td align="center"
              style="background-color:#f4f4f5;border:1px solid #d4d4d8;
                     border-radius:12px;padding:32px;">
            <span style="font-size:40px;font-weight:700;letter-spacing:14px;color:#0a0a0a;">
              {code}
            </span>
          </td>
        </tr>
      </table>

      <p style="margin:0;color:#71717a;font-size:13px;line-height:1.6;">
        If you didn't create an account, you can safely ignore this email.
      </p>
    """
    return _wrap(content)


def password_reset_email(reset_url: str) -> str:
    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Reset your password</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        We received a request to reset your password.
        This link expires in <strong style="color:#0a0a0a;">15 minutes</strong>.
      </p>

      <div style="text-align:center;margin-bottom:32px;">
        {_button("Reset Password", reset_url)}
      </div>

      {_info_box("<strong>Didn't request this?</strong> Ignore this email &mdash; your password will remain unchanged.")}

      <p style="margin:20px 0 0;color:#71717a;font-size:12px;line-height:1.6;">
        Or copy this link into your browser:<br>
        <span style="color:#3f3f46;">{reset_url}</span>
      </p>
    """
    return _wrap(content)


def password_change_request_email(confirm_url: str, deny_url: str) -> str:
    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Password change request</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        A password change was requested for your account. Was this you?
      </p>

      <!-- Confirm -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
        <tr>
          <td style="background-color:#f4f4f5;border-radius:12px;padding:20px;text-align:center;">
            <p style="margin:0 0 16px;color:#0a0a0a;font-size:14px;font-weight:600;">Yes, this was me</p>
            {_button("Confirm Password Change", confirm_url, "#0a0a0a")}
          </td>
        </tr>
      </table>

      <!-- Deny -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td style="background-color:#f4f4f5;border-radius:12px;padding:20px;text-align:center;">
            <p style="margin:0 0 16px;color:#0a0a0a;font-size:14px;font-weight:600;">No, this was not me</p>
            {_button("Deny &amp; Logout All Sessions", deny_url, "#ef4444")}
          </td>
        </tr>
      </table>

      <p style="margin:0;color:#71717a;font-size:12px;line-height:1.8;">
        This link expires in 15 minutes.<br>
        Confirm: <span style="color:#3f3f46;">{confirm_url}</span><br>
        Deny: <span style="color:#ef4444;">{deny_url}</span>
      </p>
    """
    return _wrap(content)


def password_change_denied_email() -> str:
    content = """
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Password change denied</h2>
      <p style="margin:0 0 24px;color:#71717a;font-size:15px;line-height:1.6;">
        A password change request for your account was denied and all active sessions
        have been logged out.
      </p>
    """
    return _wrap(content, header_color="#ef4444")


def tenant_verification_email(code: str) -> str:
    """HTML email sent to a tenant owner to verify their store email address."""
    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Verify your tenant email</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        Welcome to Venix. Use the code below to verify the email address for your tenant.
        It expires in <strong style="color:#0a0a0a;">10 minutes</strong>.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td align="center"
              style="background-color:#f4f4f5;border:1px solid #d4d4d8;
                     border-radius:12px;padding:32px;">
            <span style="font-size:40px;font-weight:700;letter-spacing:14px;color:#0a0a0a;">
              {code}
            </span>
          </td>
        </tr>
      </table>

      <p style="margin:0;color:#71717a;font-size:13px;line-height:1.6;">
        If you didn't register a tenant, you can safely ignore this email.
      </p>
    """
    return _wrap(content)


def tenant_password_change_code_email(code: str) -> str:
    """HTML email sent to a tenant owner with a confirmation code to complete a password change."""
    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Confirm your password change</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        A password change was requested for your tenant account. Use the code below to confirm it.
        It expires in <strong style="color:#0a0a0a;">15 minutes</strong>.
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td align="center"
              style="background-color:#f4f4f5;border:1px solid #d4d4d8;
                     border-radius:12px;padding:32px;">
            <span style="font-size:40px;font-weight:700;letter-spacing:14px;color:#0a0a0a;">
              {code}
            </span>
          </td>
        </tr>
      </table>

      {_info_box("<strong>Didn't request this?</strong> Ignore this email &mdash; your password will remain unchanged. Consider reviewing your account security.")}
    """
    return _wrap(content)


def order_confirmation_email(order_id: int, total_amount: str, items: list[dict]) -> str:
    rows = "".join([
        f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #f4f4f5;color:#0a0a0a;font-size:14px;">
            {item['name']}
          </td>
          <td style="padding:12px 0;border-bottom:1px solid #f4f4f5;color:#71717a;font-size:14px;text-align:center;">
            x{item['quantity']}
          </td>
          <td style="padding:12px 0;border-bottom:1px solid #f4f4f5;color:#0a0a0a;font-size:14px;text-align:right;font-weight:600;">
            EGP {item['subtotal']}
          </td>
        </tr>
        """
        for item in items
    ])

    content = f"""
      <h2 style="margin:0 0 8px;color:#0a0a0a;font-size:22px;font-weight:700;">Order confirmed</h2>
      <p style="margin:0 0 32px;color:#71717a;font-size:15px;line-height:1.6;">
        Thank you for your order. We're getting it ready.
      </p>

      <!-- Order ID -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr>
          <td style="background-color:#f4f4f5;border-radius:12px;padding:16px 20px;">
            <p style="margin:0;color:#71717a;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;">Order ID</p>
            <p style="margin:4px 0 0;color:#0a0a0a;font-size:16px;font-weight:700;">#{order_id}</p>
          </td>
        </tr>
      </table>

      <!-- Items table -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr>
          <th style="text-align:left;color:#71717a;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;padding-bottom:12px;border-bottom:1px solid #d4d4d8;">Item</th>
          <th style="text-align:center;color:#71717a;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;padding-bottom:12px;border-bottom:1px solid #d4d4d8;">Qty</th>
          <th style="text-align:right;color:#71717a;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;padding-bottom:12px;border-bottom:1px solid #d4d4d8;">Price</th>
        </tr>
        {rows}
      </table>

      <!-- Total -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td style="color:#0a0a0a;font-size:15px;font-weight:700;">Total</td>
          <td style="text-align:right;color:#0a0a0a;font-size:18px;font-weight:700;">EGP {total_amount}</td>
        </tr>
      </table>

      {_info_box("Your order is being prepared. You'll receive a shipping update soon.", border_color="#34d399", bg_color="#f0fdf4", text_color="#3f3f46")}
    """
    return _wrap(content)