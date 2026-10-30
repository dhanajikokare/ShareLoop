from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .models import SalesOrder, OrderItem
from listings.models import Listing
from core.models import Notification


@login_required
def create_order_view(request, listing_id):
    """
    Creates a sales order and reserves inventory safely with select_for_update to prevent overselling.
    """
    if request.method != 'POST':
        return redirect('listings:browse')

    quantity_req = int(request.POST.get('quantity', 1))
    fulfillment_type = request.POST.get('fulfillment_type', 'PICKUP')
    delivery_address = request.POST.get('delivery_address', '').strip()

    with transaction.atomic():
        # Lock row for atomic inventory check
        listing = Listing.objects.select_for_update().get(pk=listing_id)

        if not listing.can_sell or listing.status != 'ACTIVE':
            messages.error(request, "This item is no longer available for purchase.")
            return redirect('listings:browse')

        if listing.owner == request.user:
            messages.error(request, "You cannot purchase your own item.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        if listing.quantity < quantity_req:
            messages.error(request, f"Only {listing.quantity} unit(s) available in stock.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        # Deduct inventory atomically
        listing.quantity -= quantity_req
        if listing.quantity == 0:
            listing.status = 'SOLD'
        listing.save()

        items_total = listing.sell_price * Decimal(quantity_req)
        comm_pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)) / Decimal('100.00')
        platform_fee = (items_total * comm_pct).quantize(Decimal('0.01'))
        total_amount = items_total + platform_fee

        order = SalesOrder.objects.create(
            buyer=request.user,
            seller=listing.owner,
            items_total=items_total,
            platform_fee=platform_fee,
            total_amount=total_amount,
            fulfillment_type=fulfillment_type,
            delivery_address=delivery_address,
            status='CONFIRMED',
        )

        OrderItem.objects.create(
            order=order,
            listing=listing,
            unit_price=listing.sell_price,
            quantity=quantity_req,
            subtotal=items_total,
        )

        # Notify seller
        Notification.objects.create(
            user=listing.owner,
            title=f"New Purchase Order: {order.order_number}",
            message=f"{request.user.display_name} purchased {quantity_req}x '{listing.title}' for ₹{total_amount}.",
            notification_type='ORDER_PLACED',
            link_url=f"/orders/order/{order.id}/",
        )

        messages.success(request, f"Order #{order.order_number} confirmed! Coordinate handover with seller.")
        return redirect('orders:order_detail', pk=order.id)


@login_required
def my_orders_view(request):
    """
    View orders bought as buyer and orders sold as seller.
    """
    orders_bought = SalesOrder.objects.filter(buyer=request.user).prefetch_related('items__listing').order_by('-created_at')
    orders_sold = SalesOrder.objects.filter(seller=request.user).prefetch_related('items__listing').order_by('-created_at')

    context = {
        'orders_bought': orders_bought,
        'orders_sold': orders_sold,
    }
    return render(request, 'orders/my_orders.html', context)


@login_required
def order_detail_view(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.prefetch_related('items__listing'),
        pk=pk
    )

    is_buyer = request.user.id == order.buyer_id
    is_seller = request.user.id == order.seller_id
    is_staff = request.user.is_staff

    if not (is_buyer or is_seller or is_staff):
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')

    handover_logs = order.handover_logs.all().order_by('-timestamp')

    context = {
        'order': order,
        'is_buyer': is_buyer,
        'is_seller': is_seller,
        'handover_logs': handover_logs,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def update_order_status_view(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.seller != request.user and not request.user.is_staff:
        messages.error(request, "Only the seller can update order fulfillment status.")
        return redirect('orders:order_detail', pk=order.id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_transitions = ['CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'SHIPPED', 'DELIVERED', 'COMPLETED', 'CANCELLED']
        if new_status in valid_transitions:
            order.status = new_status
            order.save()

            Notification.objects.create(
                user=order.buyer,
                title=f"Order Status Update: #{order.order_number}",
                message=f"Your order status has been updated to: {order.get_status_display()}.",
                notification_type='ORDER_STATUS',
                link_url=f"/orders/order/{order.id}/",
            )
            messages.success(request, f"Order status updated to {order.get_status_display()}.")

    return redirect('orders:order_detail', pk=order.id)
