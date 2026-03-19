from django.utils import timezone
from datetime import timedelta


def notifications(request):
    if not request.user.is_authenticated:
        return {}

    company = getattr(request.user, 'company', None)
    if not company:
        return {}

    from apps.inventory.models import Inventory
    from apps.purchase_orders.models import PurchaseOrder
    from apps.suppliers.models import Farm
    from django.db.models import F

    today = timezone.now().date()
    in_30 = today + timedelta(days=30)
    in_7 = today + timedelta(days=7)

    low_stock_count = Inventory.objects.filter(
        company=company,
        quantity__lte=F('low_stock_threshold'),
    ).count()

    low_stock_items = Inventory.objects.filter(
        company=company,
        quantity__lte=F('low_stock_threshold'),
    ).select_related('product').order_by('quantity')[:5]

    overdue_count = PurchaseOrder.objects.filter(
        company=company,
        expected_delivery__lt=today,
    ).exclude(status__in=['received', 'cancelled']).count()

    upcoming_pos = PurchaseOrder.objects.filter(
        company=company,
        expected_delivery__gte=today,
        expected_delivery__lte=in_7,
    ).exclude(status__in=['received', 'cancelled']).select_related('supplier').order_by('expected_delivery')[:3]

    expiring_count = Farm.objects.filter(
        company=company,
        is_eudr_verified=True,
        verification_expiry__lte=in_30,
        verification_expiry__gte=today,
    ).count()

    expiring_farms = Farm.objects.filter(
        company=company,
        is_eudr_verified=True,
        verification_expiry__lte=in_30,
        verification_expiry__gte=today,
    ).select_related('supplier').order_by('verification_expiry')[:3]

    total_alerts = low_stock_count + overdue_count + expiring_count

    return {
        'notif_total': total_alerts,
        'notif_low_stock_count': low_stock_count,
        'notif_low_stock_items': low_stock_items,
        'notif_overdue_count': overdue_count,
        'notif_upcoming_pos': upcoming_pos,
        'notif_expiring_count': expiring_count,
        'notif_expiring_farms': expiring_farms,
    }
