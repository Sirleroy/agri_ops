"""
AgriOps Email Notifications
Called from management commands or views.
All emails are tenant-scoped and plain-text + HTML.
"""
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def _send(subject, body_text, body_html, recipient_list):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    msg.attach_alternative(body_html, "text/html")
    msg.send(fail_silently=False)


# ── Low Stock Alert ───────────────────────────────────────────
def send_low_stock_alert(inventory_item, recipient_emails):
    product = inventory_item.product
    subject = f"[AgriOps] Low Stock Alert — {product.name}"

    body_text = (
        f"Low Stock Alert\n\n"
        f"Product: {product.name}\n"
        f"Current Quantity: {inventory_item.quantity} {product.unit}\n"
        f"Low Stock Threshold: {inventory_item.low_stock_threshold} {product.unit}\n"
        f"Warehouse: {inventory_item.warehouse_location or 'Not specified'}\n\n"
        f"Please reorder to avoid supply disruption.\n\n"
        f"View inventory: https://app.agriops.io/inventory/\n\n"
        f"AgriOps · app.agriops.io"
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
      <div style="background: #0a0f1a; padding: 20px 24px; border-radius: 8px 8px 0 0;">
        <p style="color: #22c55e; font-size: 11px; letter-spacing: 3px; margin: 0 0 4px 0;">AGRIOPS</p>
        <h1 style="color: #ffffff; font-size: 20px; margin: 0;">Low Stock Alert</h1>
      </div>
      <div style="background: #ffffff; padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
        <div style="background: #fef9c3; border: 1px solid #fde047; border-radius: 6px; padding: 12px 16px; margin-bottom: 20px;">
          <p style="margin: 0; color: #854d0e; font-size: 13px;">
            ⚠ <strong>{product.name}</strong> is below the minimum stock threshold.
          </p>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr style="background: #f8fafc;">
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold; width: 40%;">Product</td>
            <td style="padding: 8px 12px; color: #1e293b;">{product.name}</td>
          </tr>
          <tr>
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Current Quantity</td>
            <td style="padding: 8px 12px; color: #ef4444; font-weight: bold;">{inventory_item.quantity} {product.unit}</td>
          </tr>
          <tr style="background: #f8fafc;">
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Threshold</td>
            <td style="padding: 8px 12px; color: #1e293b;">{inventory_item.low_stock_threshold} {product.unit}</td>
          </tr>
          <tr>
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Warehouse</td>
            <td style="padding: 8px 12px; color: #1e293b;">{inventory_item.warehouse_location or 'Not specified'}</td>
          </tr>
        </table>
        <div style="margin-top: 24px;">
          <a href="https://app.agriops.io/inventory/"
             style="background: #22c55e; color: #0a0f1a; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px;">
            View Inventory
          </a>
        </div>
        <p style="margin-top: 24px; font-size: 11px; color: #94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    _send(subject, body_text, body_html, recipient_emails)


# ── EUDR Expiry Warning ───────────────────────────────────────
def send_eudr_expiry_warning(farm, recipient_emails):
    days_left = (farm.verification_expiry - timezone.now().date()).days
    subject = f"[AgriOps] EUDR Verification Expiring — {farm.name} ({days_left} days)"

    body_text = (
        f"EUDR Verification Expiry Warning\n\n"
        f"Farm: {farm.name}\n"
        f"Supplier: {farm.supplier.name}\n"
        f"Commodity: {farm.commodity}\n"
        f"Expiry Date: {farm.verification_expiry}\n"
        f"Days Remaining: {days_left}\n\n"
        f"Please renew the EUDR verification before the expiry date "
        f"to maintain compliance status.\n\n"
        f"View farm: https://app.agriops.io/suppliers/farms/{farm.pk}/\n\n"
        f"AgriOps · app.agriops.io"
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
      <div style="background: #0a0f1a; padding: 20px 24px; border-radius: 8px 8px 0 0;">
        <p style="color: #22c55e; font-size: 11px; letter-spacing: 3px; margin: 0 0 4px 0;">AGRIOPS · EUDR COMPLIANCE</p>
        <h1 style="color: #ffffff; font-size: 20px; margin: 0;">Verification Expiry Warning</h1>
      </div>
      <div style="background: #ffffff; padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
        <div style="background: #ffedd5; border: 1px solid #fb923c; border-radius: 6px; padding: 12px 16px; margin-bottom: 20px;">
          <p style="margin: 0; color: #9a3412; font-size: 13px;">
            📅 <strong>{farm.name}</strong> EUDR verification expires in <strong>{days_left} days</strong>.
          </p>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr style="background: #f8fafc;">
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold; width: 40%;">Farm</td>
            <td style="padding: 8px 12px; color: #1e293b;">{farm.name}</td>
          </tr>
          <tr>
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Supplier</td>
            <td style="padding: 8px 12px; color: #1e293b;">{farm.supplier.name}</td>
          </tr>
          <tr style="background: #f8fafc;">
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Commodity</td>
            <td style="padding: 8px 12px; color: #1e293b;">{farm.commodity}</td>
          </tr>
          <tr>
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Expiry Date</td>
            <td style="padding: 8px 12px; color: #f97316; font-weight: bold;">{farm.verification_expiry}</td>
          </tr>
          <tr style="background: #f8fafc;">
            <td style="padding: 8px 12px; color: #64748b; font-weight: bold;">Days Remaining</td>
            <td style="padding: 8px 12px; color: #f97316; font-weight: bold;">{days_left} days</td>
          </tr>
        </table>
        <div style="margin-top: 24px;">
          <a href="https://app.agriops.io/suppliers/farms/{farm.pk}/edit/"
             style="background: #22c55e; color: #0a0f1a; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px;">
            Renew Verification
          </a>
        </div>
        <p style="margin-top: 24px; font-size: 11px; color: #94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    _send(subject, body_text, body_html, recipient_emails)


# ── User Invitation ───────────────────────────────────────────
def send_user_invitation(invited_user, invited_by, temporary_password):
    subject = f"[AgriOps] You have been invited to {invited_by.company.name}"

    body_text = (
        f"You have been invited to AgriOps\n\n"
        f"Organisation: {invited_by.company.name}\n"
        f"Invited by: {invited_by.get_full_name() or invited_by.username}\n"
        f"Your username: {invited_user.username}\n"
        f"Temporary password: {temporary_password}\n\n"
        f"Please log in and change your password immediately.\n\n"
        f"Login: https://app.agriops.io/login/\n\n"
        f"AgriOps · app.agriops.io"
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
      <div style="background: #0a0f1a; padding: 20px 24px; border-radius: 8px 8px 0 0;">
        <p style="color: #22c55e; font-size: 11px; letter-spacing: 3px; margin: 0 0 4px 0;">AGRIOPS</p>
        <h1 style="color: #ffffff; font-size: 20px; margin: 0;">You have been invited</h1>
      </div>
      <div style="background: #ffffff; padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="color: #1e293b; font-size: 14px;">
          <strong>{invited_by.get_full_name() or invited_by.username}</strong> has invited you to join
          <strong>{invited_by.company.name}</strong> on AgriOps.
        </p>
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 16px; margin: 20px 0;">
          <table style="width: 100%; font-size: 13px;">
            <tr>
              <td style="color: #64748b; font-weight: bold; padding: 4px 0; width: 40%;">Username</td>
              <td style="color: #1e293b; font-family: monospace;">{invited_user.username}</td>
            </tr>
            <tr>
              <td style="color: #64748b; font-weight: bold; padding: 4px 0;">Temporary Password</td>
              <td style="color: #1e293b; font-family: monospace;">{temporary_password}</td>
            </tr>
            <tr>
              <td style="color: #64748b; font-weight: bold; padding: 4px 0;">Organisation</td>
              <td style="color: #1e293b;">{invited_by.company.name}</td>
            </tr>
          </table>
        </div>
        <div style="background: #fef9c3; border: 1px solid #fde047; border-radius: 6px; padding: 10px 14px; margin-bottom: 20px;">
          <p style="margin: 0; color: #854d0e; font-size: 12px;">
            ⚠ Please change your password immediately after first login.
          </p>
        </div>
        <a href="https://app.agriops.io/login/"
           style="background: #22c55e; color: #0a0f1a; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px;">
          Log In to AgriOps
        </a>
        <p style="margin-top: 24px; font-size: 11px; color: #94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    _send(subject, body_text, body_html, [invited_user.email])
