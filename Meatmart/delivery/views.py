from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.utils import timezone
import json

from .models import DeliveryProfile
from orders.models import Order
from accounts.models import User

def is_delivery_boy(user):
    return user.is_authenticated and user.role == User.Role.DELIVERY_BOY

def delivery_register(request):
    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        vehicle_type = request.POST.get('vehicle_type')
        vehicle_number = request.POST.get('vehicle_number')
        license_number = request.POST.get('license_number')
        
        # Validate form data
        if not all([email, password, password_confirm, first_name, last_name, phone, vehicle_type, vehicle_number, license_number]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('delivery:register')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('delivery:register')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('delivery:register')
        
        try:
            # Generate username from email (everything before @)
            username = email.split('@')[0]
            base_username = username
            counter = 1
            
            # If username exists, append a number until we find a unique one
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.DELIVERY_BOY
            )
            
            # Create delivery profile
            profile = DeliveryProfile.objects.create(
                user=user,
                phone=phone,
                vehicle_type=vehicle_type,
                vehicle_number=vehicle_number,
                license_number=license_number,
                status='OFFLINE'
            )
            
            # Handle file uploads
            if 'license_image' in request.FILES:
                profile.license_image = request.FILES['license_image']
                profile.save()
            
            messages.success(request, 'Registration successful! Please login.')
            return redirect('delivery:login')
            
        except Exception as e:
            # If there's an error, delete the user if it was created
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Error creating account: {str(e)}')
            return redirect('delivery:register')
    
    # GET request - show registration form
    return render(request, 'delivery/register.html', {
        'vehicle_types': DeliveryProfile.VEHICLE_TYPES
    })

def delivery_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            if hasattr(user, 'delivery_profile'):
                login(request, user)
                messages.success(request, 'Welcome back!')
                return redirect('delivery:dashboard')
            else:
                messages.error(request, 'This account is not registered as a delivery partner.')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'delivery/login.html')

@login_required
def dashboard(request):
    today = timezone.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    # Get delivery counts
    today_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=today_start
    ).count()

    month_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=month_start
    ).count()

    # Calculate earnings (₹50 per delivery)
    todays_earnings = today_deliveries * 50

    # Get active orders
    active_orders = Order.objects.filter(
        delivery_boy=request.user,
        status__in=['ASSIGNED', 'ACCEPTED', 'OUT_FOR_DELIVERY']
    ).select_related('user', 'delivery_address').prefetch_related('items').order_by('-created_at')

    # Get delivery boy profile
    try:
        profile = DeliveryProfile.objects.get(user=request.user)
    except DeliveryProfile.DoesNotExist:
        profile = DeliveryProfile.objects.create(user=request.user, status='OFFLINE')

    # Prepare chart data
    last_30_days = today - timezone.timedelta(days=29)
    daily_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=last_30_days
    ).annotate(
        date_delivered=TruncDate('delivered_at')
    ).values('date_delivered').annotate(
        count=Count('id')
    ).order_by('date_delivered')

    dates = [(last_30_days + timezone.timedelta(days=x)).date() for x in range(30)]
    delivery_counts = {d['date_delivered']: d['count'] for d in daily_deliveries}
    chart_data = [delivery_counts.get(date, 0) for date in dates]
    chart_labels = [date.strftime('%b %d') for date in dates]

    context = {
        'profile': profile,
        'active_orders': active_orders,
        'today_deliveries': today_deliveries,
        'month_deliveries': month_deliveries,
        'todays_earnings': todays_earnings,
        'chart_data': chart_data,
        'chart_labels': chart_labels,
    }

    return render(request, 'delivery/dashboard.html', context)

@login_required
def orders(request):
    # Get assigned and accepted orders
    active_orders = Order.objects.filter(
        delivery_boy=request.user,
        status__in=['ASSIGNED', 'ACCEPTED', 'OUT_FOR_DELIVERY']
    ).select_related(
        'user', 
        'delivery_address'
    ).order_by('-created_at')
    
    return render(request, 'delivery/orders.html', {
        'orders': active_orders,
    })

@login_required
def accept_order(request, order_id):
    """Accept an assigned order."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        order = Order.objects.get(id=order_id, delivery_boy=request.user, status='ASSIGNED')
        order.status = 'ACCEPTED'
        order.save()
        
        # Update delivery boy status
        request.user.delivery_profile.status = 'BUSY'
        request.user.delivery_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Order accepted successfully'
        })
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found or cannot be accepted'
        }, status=404)

@login_required
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
def update_delivery_status(request, order_id):
    """Update delivery status of an accepted order."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        order = Order.objects.get(
            id=order_id, 
            delivery_boy=request.user, 
            status__in=['ACCEPTED', 'OUT_FOR_DELIVERY']
        )
        
        new_status = request.POST.get('status')
        if new_status not in ['OUT_FOR_DELIVERY', 'DELIVERED']:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
        
        order.status = new_status
        if new_status == 'DELIVERED':
            order.delivered_at = timezone.now()
            # Update delivery boy status back to available
            request.user.delivery_profile.status = 'AVAILABLE'
            request.user.delivery_profile.save()
            
        order.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Order marked as {new_status}'
        })
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found or cannot be updated'
        }, status=404)

@login_required
def history(request):
    completed_orders = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED'
    ).select_related(
        'user',
        'delivery_address'
    ).prefetch_related(
        'items',
        'items__product'
    ).order_by('-delivered_at')
    
    return render(request, 'delivery/history.html', {
        'orders': completed_orders,
    })

@login_required
def earnings(request):
    # Get earnings for different time periods
    today = timezone.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timezone.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # Calculate earnings (₹50 per delivery)
    today_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=today_start
    ).count()
    
    week_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=week_start
    ).count()
    
    month_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivered_at__gte=month_start
    ).count()
    
    earnings_data = {
        'today': today_deliveries * 50,  # ₹50 per delivery
        'week': week_deliveries * 50,
        'month': month_deliveries * 50,
        'total_deliveries': {
            'today': today_deliveries,
            'week': week_deliveries,
            'month': month_deliveries
        }
    }
    
    return render(request, 'delivery/earnings.html', earnings_data)

@login_required
@user_passes_test(is_delivery_boy)
def profile(request):
    delivery_profile = request.user.delivery_profile
    
    if request.method == 'POST':
        try:
            # Update user information
            request.user.first_name = request.POST.get('first_name')
            request.user.last_name = request.POST.get('last_name')
            request.user.email = request.POST.get('email')
            request.user.save()
            
            # Update delivery profile
            delivery_profile.phone = request.POST.get('phone')
            delivery_profile.address = request.POST.get('address')
            delivery_profile.vehicle_type = request.POST.get('vehicle_type')
            delivery_profile.vehicle_number = request.POST.get('vehicle_number')
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                if delivery_profile.profile_picture:
                    # Delete old profile picture if it exists
                    delivery_profile.profile_picture.delete(save=False)
                delivery_profile.profile_picture = request.FILES['profile_picture']
            
            delivery_profile.save()
            messages.success(request, 'Profile updated successfully!')
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            
        return redirect('delivery:profile')
    
    # Get statistics for the profile page
    total_deliveries = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED'
    ).count()
    
    total_earnings = total_deliveries * 50  # ₹50 per delivery
    
    avg_rating = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED',
        delivery_rating__isnull=False
    ).aggregate(Avg('delivery_rating'))['delivery_rating__avg'] or 0
    
    context = {
        'delivery_profile': delivery_profile,
        'total_deliveries': total_deliveries,
        'total_earnings': total_earnings,
        'avg_rating': round(avg_rating, 1),
        'VEHICLE_TYPES': DeliveryProfile.VEHICLE_TYPES,
    }
    
    return render(request, 'delivery/profile.html', context)

@login_required
def settings(request):
    if request.method == 'POST':
        # Handle settings update
        profile = request.user.delivery_profile
        profile.notification_enabled = request.POST.get('notifications') == 'on'
        profile.save()
        messages.success(request, 'Settings updated successfully!')
        return redirect('delivery:settings')
    
    return render(request, 'delivery/settings.html', {
        'profile': request.user.delivery_profile
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, delivery_boy=request.user)
    return render(request, 'delivery/order_detail.html', {
        'order': order
    })

@login_required
def update_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            # Validate the status
            valid_statuses = [status[0] for status in DeliveryProfile.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status'
                })
            
            # Update the delivery profile
            profile = request.user.delivery_profile
            profile.status = new_status
            profile.save()
            
            return JsonResponse({
                'success': True,
                'status': profile.get_status_display()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
            
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })

@login_required
def update_availability(request):
    """Update delivery boy availability status."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        status = data.get('status')
        
        if status not in ['AVAILABLE', 'OFFLINE']:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
        
        # Update delivery boy profile status
        delivery_profile = request.user.delivery_profile
        delivery_profile.status = status
        delivery_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Status updated to {status}'
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
    active_orders = Order.objects.filter(
        delivery_boy=request.user,
        status__in=['ASSIGNED', 'PICKED_UP', 'OUT_FOR_DELIVERY']
    ).order_by('-created_at')
    
    completed_orders = Order.objects.filter(
        delivery_boy=request.user,
        status='DELIVERED'
    ).order_by('-delivered_at')[:10]  # Show last 10 completed orders
    
    context = {
        'active_orders': active_orders,
        'completed_orders': completed_orders
    }
    
    return render(request, 'delivery/my_orders.html', context)
