from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from orders.models import Order
from django.utils import timezone

# Create your views here.

def is_delivery_boy(user):
    return user.role == 'DELIVERY_BOY'

@login_required
@user_passes_test(is_delivery_boy)
def reject_order(request, order_id):
    """Allow delivery boy to reject an assigned order with a reason."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        order = get_object_or_404(Order, id=order_id, delivery_boy=request.user)
        rejection_reason = request.POST.get('rejection_reason')
        
        if not rejection_reason:
            return JsonResponse({
                'status': 'error',
                'message': 'Rejection reason is required'
            }, status=400)
        
        # Check if order is in a valid state to be rejected
        if order.status != 'ASSIGNED':
            return JsonResponse({
                'status': 'error',
                'message': f'Order cannot be rejected in {order.status} state'
            }, status=400)
        
        # Update order status and add rejection reason
        order.status = 'REJECTED'
        order.rejection_reason = rejection_reason
        order.delivery_boy = None  # Remove delivery boy assignment
        order.save()
        
        # Update delivery boy status to available
        request.user.delivery_profile.status = 'AVAILABLE'
        request.user.delivery_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Order rejected successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@user_passes_test(is_delivery_boy)
def my_orders(request):
    """View for delivery boy to see their assigned orders."""
    orders = Order.objects.filter(delivery_boy=request.user).order_by('-created_at')
    
    context = {
        'orders': orders,
        'title': 'My Orders'
    }
    
    return render(request, 'delivery_boy/orders.html', context)
