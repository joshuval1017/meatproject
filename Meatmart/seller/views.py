from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Q, F
from products.models import Product, Category, StockHistory, StockAlert
from orders.models import Order, OrderItem
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from decimal import Decimal
from accounts.models import User  # Import User from accounts app
from django.http import JsonResponse

# Create your views here.

def is_seller(user):
    return user.is_seller

@login_required
@user_passes_test(is_seller)
def dashboard(request):
    """Seller dashboard view."""
    today = timezone.now().date()
    last_30_days = today - timedelta(days=29)

    # Get seller's products
    products = Product.objects.filter(seller=request.user)
    
    # Product statistics
    active_products = products.filter(is_available=True).count()
    total_products = products.count()
    pending_products = products.filter(is_approved=False).count()
    
    # Stock statistics
    low_stock_products = products.filter(stock_quantity__lte=10).count()
    out_of_stock_products = products.filter(stock_quantity=0).count()
    
    # Order statistics
    order_items = OrderItem.objects.filter(product__seller=request.user)
    orders_today = order_items.filter(order__created_at__date=today).count()
    total_orders = order_items.count()
    
    # Revenue statistics (price_per_kg * quantity)
    revenue_today = order_items.filter(
        order__created_at__date=today,
        order__status='DELIVERED'
    ).aggregate(
        total=Sum('total')
    )['total'] or 0
    
    total_revenue = order_items.filter(
        order__status='DELIVERED'
    ).aggregate(
        total=Sum('total')
    )['total'] or 0
    
    # Get recent orders
    recent_orders = Order.objects.filter(
        items__product__seller=request.user
    ).distinct().order_by('-created_at')[:5]

    # Get sales by category for donut chart
    category_sales = Category.objects.filter(
        product__seller=request.user,
        product__order_items__order__status='DELIVERED'
    ).annotate(
        total_sales=Sum('product__order_items__total')
    ).values('name', 'total_sales').order_by('-total_sales')
    
    # Prepare category chart data
    chart_categories = []
    chart_values = []
    for cat in category_sales:
        if cat['total_sales']:  # Only include categories with sales
            chart_categories.append(cat['name'])
            chart_values.append(float(cat['total_sales']))

    # Get daily sales data for line chart
    daily_sales = OrderItem.objects.filter(
        product__seller=request.user,
        order__created_at__date__gte=last_30_days,
        order__status='DELIVERED'
    ).values('order__created_at__date').annotate(
        total_sales=Sum('total')
    ).order_by('order__created_at__date')

    # Prepare line chart data
    dates = []
    sales_amounts = []
    
    # Initialize all dates with 0 sales
    current_date = last_30_days
    while current_date <= today:
        dates.append(current_date.strftime('%Y-%m-%d'))
        sales_amounts.append(0)
        current_date += timedelta(days=1)

    # Fill in actual sales data
    for sale in daily_sales:
        date_str = sale['order__created_at__date'].strftime('%Y-%m-%d')
        if date_str in dates:
            index = dates.index(date_str)
            sales_amounts[index] = float(sale['total_sales'])
    
    context = {
        'title': 'Seller Dashboard',
        'user': request.user,
        'active_products': active_products,
        'total_products': total_products,
        'pending_products': pending_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'orders_today': orders_today,
        'total_orders': total_orders,
        'revenue_today': revenue_today,
        'total_revenue': total_revenue,
        'recent_orders': recent_orders,
        'chart_categories': chart_categories,
        'chart_values': chart_values,
        'chart_data': {
            'dates': dates,
            'amounts': sales_amounts,
        }
    }
    return render(request, 'seller/dashboard.html', context)

@login_required
@user_passes_test(is_seller)
def product_list(request):
    """List seller's products."""
    # Get filter parameters
    category_id = request.GET.get('category')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    # Base queryset
    products = Product.objects.filter(seller=request.user)
    
    # Apply filters
    if category_id:
        products = products.filter(category_id=category_id)
    
    if status:
        if status == 'active':
            products = products.filter(is_available=True, is_approved=True)
        elif status == 'pending':
            products = products.filter(is_approved=False)
        elif status == 'unavailable':
            products = products.filter(is_available=False)
    
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Get all categories for the filter dropdown
    categories = Category.objects.all()
    
    context = {
        'title': 'My Products',
        'products': products,
        'categories': categories,
    }
    return render(request, 'seller/products.html', context)

@login_required
@user_passes_test(is_seller)
def order_list(request):
    """List seller's orders."""
    # Get filter parameters
    status = request.GET.get('status')
    search = request.GET.get('search')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    orders = Order.objects.filter(
        items__product__seller=request.user
    ).distinct().order_by('-created_at')
    
    # Apply filters
    if status:
        orders = orders.filter(status=status)
    
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(buyer__email__icontains=search) |
            Q(buyer__company_name__icontains=search)
        )
    
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    
    context = {
        'title': 'My Orders',
        'orders': orders,
    }
    return render(request, 'seller/orders.html', context)

@login_required
@user_passes_test(is_seller)
def confirm_order(request, order_id):
    """Confirm a pending order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if the order contains products from this seller
    if not order.items.filter(product__seller=request.user).exists():
        messages.error(request, "You don't have permission to confirm this order.")
        return redirect('seller:orders')
    
    if order.status != 'PENDING':
        messages.error(request, "This order cannot be confirmed because it is not pending.")
        return redirect('seller:orders')
    
    # Update order status
    order.status = 'CONFIRMED'
    order.save()
    
    messages.success(request, f"Order #{order.order_number} has been confirmed successfully.")
    return redirect('seller:orders')

@login_required
@user_passes_test(is_seller)
def process_order(request, order_id):
    """Process a confirmed order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if any of the order items belong to this seller
    if not order.items.filter(product__seller=request.user).exists():
        messages.error(request, "You don't have permission to process this order.")
        return redirect('seller:orders')
    
    # Check if order is in correct status
    if order.status != 'CONFIRMED':
        messages.error(request, "This order cannot be processed at this time.")
        return redirect('seller:orders')
    
    # Update order status
    order.status = 'PROCESSING'
    order.save()
    
    messages.success(request, f"Order #{order.order_number} is now being processed.")
    return redirect('seller:orders')

@login_required
@user_passes_test(is_seller)
def ship_order(request, order_id):
    """Mark order as shipped."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if any of the order items belong to this seller
    if not order.items.filter(product__seller=request.user).exists():
        messages.error(request, "You don't have permission to ship this order.")
        return redirect('seller:orders')
    
    # Check if order is in correct status
    if order.status != 'PROCESSING':
        messages.error(request, "This order cannot be shipped at this time.")
        return redirect('seller:orders')
    
    # Update order status
    order.status = 'SHIPPED'
    order.save()
    
    messages.success(request, f"Order #{order.order_number} has been marked as shipped.")
    return redirect('seller:orders')

@login_required
@user_passes_test(is_seller)
def deliver_order(request, order_id):
    """Mark order as delivered."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if any of the order items belong to this seller
    if not order.items.filter(product__seller=request.user).exists():
        messages.error(request, "You don't have permission to mark this order as delivered.")
        return redirect('seller:orders')
    
    # Check if order is in correct status
    if order.status != 'SHIPPED':
        messages.error(request, "This order cannot be marked as delivered at this time.")
        return redirect('seller:orders')
    
    # Update order status
    order.status = 'DELIVERED'
    order.save()
    
    messages.success(request, f"Order #{order.order_number} has been marked as delivered.")
    return redirect('seller:orders')

@login_required
@user_passes_test(is_seller)
def cancel_order(request, order_id):
    """Cancel an order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if any of the order items belong to this seller
    if not order.items.filter(product__seller=request.user).exists():
        messages.error(request, "You don't have permission to cancel this order.")
        return redirect('seller:orders')
    
    # Check if order can be cancelled
    if order.status in ['DELIVERED', 'CANCELLED']:
        messages.error(request, "This order cannot be cancelled.")
        return redirect('seller:orders')
    
    # Update order status
    order.status = 'CANCELLED'
    order.save()
    
    messages.success(request, f"Order #{order.order_number} has been cancelled.")
    return redirect('seller:orders')

@login_required
@user_passes_test(is_seller)
def analytics(request):
    """Show seller analytics."""
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)  # Default to last 30 days
    
    # Handle custom date range
    date_range = request.GET.get('range')
    if date_range:
        if date_range == '7':
            start_date = end_date - timedelta(days=7)
        elif date_range == '90':
            start_date = end_date - timedelta(days=90)
        elif date_range == 'custom':
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            if start_date and end_date:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get sales statistics
    sales_stats = OrderItem.objects.filter(
        product__seller=request.user,
        order__created_at__date__range=[start_date, end_date],
        order__status='DELIVERED'
    ).aggregate(
        total_amount=Sum('total'),
        total_quantity=Sum('quantity'),
        total_orders=Count('order', distinct=True),
        unique_buyers=Count('order__user', distinct=True)
    )
    
    # Calculate average order value
    if sales_stats['total_amount'] and sales_stats['total_orders']:
        sales_stats['avg_order_value'] = sales_stats['total_amount'] / sales_stats['total_orders']
    else:
        sales_stats['avg_order_value'] = 0
    
    # Get daily sales data for chart
    daily_sales = OrderItem.objects.filter(
        product__seller=request.user,
        order__created_at__date__range=[start_date, end_date],
        order__status='DELIVERED'
    ).values('order__created_at__date').annotate(
        amount=Sum('total'),
        orders=Count('order', distinct=True),
        quantity=Sum('quantity')
    ).order_by('order__created_at__date')

    # Prepare chart data
    dates = []
    amounts = []
    orders = []
    quantities = []
    for sale in daily_sales:
        dates.append(sale['order__created_at__date'].strftime('%Y-%m-%d'))
        amounts.append(float(sale['amount'] or 0))
        orders.append(sale['orders'])
        quantities.append(float(sale['quantity'] or 0))
    
    # Get top products
    top_products = Product.objects.filter(
        seller=request.user,
        order_items__order__status='DELIVERED',
        order_items__order__created_at__date__range=[start_date, end_date]
    ).annotate(
        total_sales=Sum('order_items__total'),
        total_quantity=Sum('order_items__quantity'),
        order_count=Count('order_items__order', distinct=True)
    ).order_by('-total_sales')[:10]
    
    # Get revenue by category
    revenue_by_category = Category.objects.filter(
        product__seller=request.user,
        product__order_items__order__status='DELIVERED',
        product__order_items__order__created_at__date__range=[start_date, end_date]
    ).annotate(
        total_sales=Sum('product__order_items__total'),
        total_quantity=Sum('product__order_items__quantity'),
        product_count=Count('product', distinct=True)
    ).order_by('-total_sales')

    # Calculate percentage for each category
    total_sales = sum(cat.total_sales or 0 for cat in revenue_by_category)
    for category in revenue_by_category:
        if total_sales > 0:
            category.sales_percentage = (category.total_sales or 0) / total_sales * 100
        else:
            category.sales_percentage = 0
    
    context = {
        'title': 'Analytics',
        'start_date': start_date,
        'end_date': end_date,
        'sales_stats': sales_stats,
        'chart_data': {
            'dates': dates,
            'amounts': amounts,
            'orders': orders,
            'quantities': quantities
        },
        'top_products': top_products,
        'revenue_by_category': revenue_by_category,
    }
    return render(request, 'seller/analytics.html', context)

@login_required
@user_passes_test(is_seller)
def download_report(request, report_type):
    """Generate and download sales or products report."""
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)  # Default to last 30 days
    
    # Handle custom date range
    date_range = request.GET.get('range')
    if date_range:
        if date_range == '7':
            start_date = end_date - timedelta(days=7)
        elif date_range == '90':
            start_date = end_date - timedelta(days=90)
        elif date_range == 'custom':
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            if start_date and end_date:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
    
    import csv
    from django.http import HttpResponse
    
    if report_type == 'sales':
        # Generate sales report
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_to_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Order Number', 'Product', 'Quantity (kg)', 'Price per kg', 'Total'])
        
        order_items = OrderItem.objects.filter(
            product__seller=request.user,
            order__created_at__date__range=[start_date, end_date],
            order__status='DELIVERED'
        ).select_related('order', 'product').order_by('order__created_at')
        
        for item in order_items:
            writer.writerow([
                item.order.created_at.strftime('%Y-%m-%d'),
                item.order.order_number,
                item.product.name,
                item.quantity,
                item.price_per_kg,
                item.total
            ])
        
        return response
    
    elif report_type == 'products':
        # Generate products report
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="products_report_{start_date}_to_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Product', 'Category', 'Total Sales', 'Total Quantity', 'Orders'])
        
        products = Product.objects.filter(
            seller=request.user,
            order_items__order__status='DELIVERED',
            order_items__order__created_at__date__range=[start_date, end_date]
        ).annotate(
            total_sales=Sum('order_items__total'),
            total_quantity=Sum('order_items__quantity'),
            order_count=Count('order_items__order', distinct=True)
        ).select_related('category')
        
        for product in products:
            writer.writerow([
                product.name,
                product.category.name,
                product.total_sales or 0,
                product.total_quantity or 0,
                product.order_count
            ])
        
        return response
    
    messages.error(request, "Invalid report type.")
    return redirect('seller:analytics')

@login_required
@user_passes_test(is_seller)
def profile(request):
    """Show seller profile."""
    context = {
        'title': 'My Profile',
        'user': request.user,
    }
    return render(request, 'seller/profile.html', context)

@login_required
@user_passes_test(is_seller)
def settings(request):
    """Show seller settings."""
    context = {
        'title': 'Settings',
        'user': request.user,
    }
    return render(request, 'seller/settings.html', context)

@login_required
@user_passes_test(is_seller)
def update_notification_settings(request):
    """Update seller notification settings."""
    if request.method == 'POST':
        # Update notification settings
        request.user.seller_profile.email_order_updates = request.POST.get('email_order_updates', False) == 'on'
        request.user.seller_profile.email_product_updates = request.POST.get('email_product_updates', False) == 'on'
        request.user.seller_profile.email_marketing = request.POST.get('email_marketing', False) == 'on'
        request.user.seller_profile.save()
        
        messages.success(request, "Notification settings updated successfully.")
    
    return redirect('seller:settings')

@login_required
@user_passes_test(is_seller)
def update_payment_settings(request):
    """Update seller payment settings."""
    if request.method == 'POST':
        # Update payment settings
        request.user.seller_profile.bank_name = request.POST.get('bank_name', '')
        request.user.seller_profile.account_number = request.POST.get('account_number', '')
        request.user.seller_profile.ifsc_code = request.POST.get('ifsc_code', '')
        request.user.seller_profile.save()
        
        messages.success(request, "Payment settings updated successfully.")
    
    return redirect('seller:settings')

@login_required
@user_passes_test(is_seller)
def update_shipping_settings(request):
    """Update seller shipping settings."""
    if request.method == 'POST':
        # Update shipping settings
        request.user.seller_profile.default_shipping_method = request.POST.get('default_shipping_method', '')
        request.user.seller_profile.free_shipping_threshold = request.POST.get('free_shipping_threshold', 0)
        request.user.seller_profile.save()
        
        messages.success(request, "Shipping settings updated successfully.")
    
    return redirect('seller:settings')

@login_required
@user_passes_test(is_seller)
def update_tax_settings(request):
    """Update seller tax settings."""
    if request.method == 'POST':
        # Update tax settings
        request.user.seller_profile.gst_number = request.POST.get('gst_number', '')
        request.user.seller_profile.pan_number = request.POST.get('pan_number', '')
        request.user.seller_profile.save()
        
        messages.success(request, "Tax settings updated successfully.")
    
    return redirect('seller:settings')

@login_required
@user_passes_test(is_seller)
def update_privacy_settings(request):
    """Update seller privacy settings."""
    if request.method == 'POST':
        # Update privacy settings
        request.user.seller_profile.show_contact_info = request.POST.get('show_contact_info', False) == 'on'
        request.user.seller_profile.show_business_info = request.POST.get('show_business_info', False) == 'on'
        request.user.seller_profile.save()
        
        messages.success(request, "Privacy settings updated successfully.")
    
    return redirect('seller:settings')

@login_required
@user_passes_test(is_seller)
def add_product(request):
    """Add a new product."""
    if request.method == 'POST':
        try:
            product = Product.objects.create(
                seller=request.user,
                name=request.POST.get('name'),
                description=request.POST.get('description'),
                category_id=request.POST.get('category'),
                price_per_kg=request.POST.get('price_per_kg'),
                minimum_order_quantity=request.POST.get('minimum_order_quantity'),
                stock_quantity=request.POST.get('stock_quantity'),
                image=request.FILES.get('image'),
                is_available=True,
                is_approved=False  # Seller-created products need admin approval
            )
            messages.success(request, f'Product "{product.name}" has been added and is pending approval.')
            return redirect('seller:products')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
    
    return redirect('seller:products')

@login_required
@user_passes_test(is_seller)
def edit_product(request, product_id):
    """Edit an existing product."""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        try:
            product.name = request.POST.get('name')
            product.description = request.POST.get('description')
            product.category_id = request.POST.get('category')
            product.price_per_kg = request.POST.get('price_per_kg')
            product.minimum_order_quantity = request.POST.get('minimum_order_quantity')
            product.stock_quantity = request.POST.get('stock_quantity')
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            
            product.is_available = bool(request.POST.get('is_available'))
            product.save()
            
            messages.success(request, f'Product "{product.name}" has been updated.')
            return redirect('seller:products')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
    
    return redirect('seller:products')

@login_required
@user_passes_test(is_seller)
def toggle_product(request, product_id):
    """Toggle product availability."""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    product.is_available = not product.is_available
    product.save()
    
    status = "available" if product.is_available else "unavailable"
    messages.success(request, f'Product "{product.name}" is now {status}.')
    return redirect('seller:products')

@login_required
@user_passes_test(is_seller)
def stock_management(request):
    """Display and manage stock for all seller's products."""
    products = Product.objects.filter(seller=request.user).order_by('-created_at')
    categories = Category.objects.all()
    
    # Handle search
    query = request.GET.get('q')
    if query:
        products = products.filter(name__icontains=query)
    
    # Handle filters
    stock_filter = request.GET.get('stock_status')
    if stock_filter:
        if stock_filter == 'low':
            products = products.filter(stock_quantity__lte=10)
        elif stock_filter == 'out':
            products = products.filter(stock_quantity=0)
        elif stock_filter == 'in':
            products = products.filter(stock_quantity__gt=10)
    
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Pagination
    paginator = Paginator(products, 10)
    page = request.GET.get('page')
    products = paginator.get_page(page)
    
    context = {
        'products': products,
        'categories': categories,
        'stock_filter': stock_filter,
        'search_query': query
    }
    return render(request, 'seller/stock_management.html', context)

@login_required
@user_passes_test(is_seller)
def update_stock(request, product_id):
    """Update stock quantity for a specific product."""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        quantity = Decimal(request.POST.get('quantity', 0))
        change_type = request.POST.get('change_type')
        reason = request.POST.get('reason')
        
        if change_type == 'ADDITION':
            new_quantity = product.stock_quantity + quantity
        elif change_type == 'REDUCTION':
            new_quantity = product.stock_quantity - quantity
            if new_quantity < 0:
                messages.error(request, "Stock cannot be reduced below 0.")
                return redirect('seller:stock_management')
        else:  # ADJUSTMENT
            new_quantity = quantity
        
        # Create stock history record
        StockHistory.objects.create(
            product=product,
            change_type=change_type,
            previous_quantity=product.stock_quantity,
            new_quantity=new_quantity,
            change_reason=reason,
            changed_by=request.user
        )
        
        # Update product stock
        product.stock_quantity = new_quantity
        product.save()
        
        messages.success(request, f"Stock updated successfully for {product.name}")
        
    return redirect('seller:stock_management')

@login_required
@user_passes_test(is_seller)
def set_stock_alert(request, product_id):
    """Set stock alert threshold for a specific product."""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        threshold = Decimal(request.POST.get('threshold_quantity', 0))
        is_active = request.POST.get('is_active') == 'on'
        
        alert, created = StockAlert.objects.get_or_create(
            product=product,
            defaults={'threshold_quantity': threshold, 'is_active': is_active}
        )
        
        if not created:
            alert.threshold_quantity = threshold
            alert.is_active = is_active
            alert.save()
        
        messages.success(request, f"Stock alert settings updated for {product.name}")
    
    return redirect('seller:stock_management')

@login_required
@user_passes_test(is_seller)
def delivery_boys(request):
    """View list of delivery boys and their status."""
    status = request.GET.get('status')
    
    # Get all delivery boys
    delivery_boys_list = User.objects.filter(
        role='DELIVERY_BOY'
    ).select_related('delivery_profile')
    
    # Apply status filter if provided
    if status:
        if status == 'available':
            delivery_boys_list = delivery_boys_list.filter(delivery_profile__status='AVAILABLE')
        elif status == 'busy':
            delivery_boys_list = delivery_boys_list.filter(delivery_profile__status='BUSY')
        elif status == 'offline':
            delivery_boys_list = delivery_boys_list.filter(delivery_profile__status='OFFLINE')
        elif status == 'break':
            delivery_boys_list = delivery_boys_list.filter(delivery_profile__status='BREAK')
    
    # Paginate results
    paginator = Paginator(delivery_boys_list, 12)  # Show 12 delivery boys per page
    page = request.GET.get('page')
    delivery_boys = paginator.get_page(page)
    
    context = {
        'delivery_boys': delivery_boys,
        'status': status,
    }
    
    return render(request, 'seller/delivery_boys.html', context)

@login_required
@user_passes_test(is_seller)
def delivery_boy_details(request, delivery_boy_id):
    """Get detailed information about a delivery boy."""
    try:
        delivery_boy = User.objects.select_related('delivery_profile').get(
            id=delivery_boy_id, 
            role='DELIVERY_BOY'
        )
        profile = delivery_boy.delivery_profile
        
        # Get recent deliveries
        recent_deliveries = Order.objects.filter(
            delivery_boy=delivery_boy
        ).order_by('-created_at')[:5].values(
            'id', 'status', 'created_at'
        )
        
        # Format the data for JSON response
        data = {
            'status': 'success',
            'name': delivery_boy.get_full_name(),
            'email': delivery_boy.email,
            'phone_number': profile.phone_number if profile else 'N/A',
            'rating': float(profile.rating) if profile and profile.rating else None,
            'total_deliveries': Order.objects.filter(delivery_boy=delivery_boy, status='DELIVERED').count(),
            'current_location': profile.current_location if profile else None,
            'profile_picture': delivery_boy.profile_picture.url if delivery_boy.profile_picture else None,
            'recent_deliveries': [{
                'order_id': delivery['id'],
                'status': delivery['status'],
                'date': delivery['created_at'].strftime('%Y-%m-%d %H:%M')
            } for delivery in recent_deliveries]
        }
        
        return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Delivery boy not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@user_passes_test(is_seller)
def available_delivery_boys(request):
    """Get list of available delivery boys."""
    delivery_boys = User.objects.filter(
        role='DELIVERY_BOY',
        delivery_profile__status='AVAILABLE'
    ).select_related('delivery_profile')
    
    data = {
        'status': 'success',
        'delivery_boys': [{
            'id': boy.id,
            'name': boy.get_full_name(),
            'rating': float(boy.delivery_profile.rating) if boy.delivery_profile.rating else None,
            'total_deliveries': boy.delivery_profile.total_deliveries
        } for boy in delivery_boys]
    }
    
    return JsonResponse(data)

@login_required
@user_passes_test(is_seller)
def assign_delivery_boy(request, order_id):
    """Assign a delivery boy to an order."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        order = Order.objects.get(id=order_id)
        delivery_boy_id = request.POST.get('delivery_boy_id')
        
        if not delivery_boy_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Delivery boy ID is required'
            }, status=400)
        
        delivery_boy = User.objects.get(id=delivery_boy_id, role='DELIVERY_BOY')
        
        # Check if delivery boy is available
        if delivery_boy.delivery_profile.status != 'AVAILABLE':
            return JsonResponse({
                'status': 'error',
                'message': 'Selected delivery boy is not available'
            }, status=400)
        
        # Check if order is in a valid state to be assigned
        valid_states = ['CONFIRMED', 'REJECTED']  # Can assign if confirmed or previously rejected
        if order.status not in valid_states:
            return JsonResponse({
                'status': 'error',
                'message': f'Order cannot be assigned in {order.status} state'
            }, status=400)
        
        # Assign delivery boy and update status
        order.delivery_boy = delivery_boy
        order.status = 'ASSIGNED'
        order.save()
        
        # Send notification to delivery boy (implement your notification system)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Delivery boy assigned successfully'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found'
        }, status=404)
    except User.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Delivery boy not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def update_order_status(request, order_id):
    """Update order status by delivery boy."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    if not request.user.role == 'DELIVERY_BOY':
        return JsonResponse({
            'status': 'error',
            'message': 'Only delivery boys can update order status'
        }, status=403)
    
    try:
        order = Order.objects.get(id=order_id, delivery_boy=request.user)
        new_status = request.POST.get('status')
        
        valid_statuses = ['TRAVELLING', 'DELIVERED', 'NOT_DELIVERED']
        if new_status not in valid_statuses:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
        
        order.status = new_status
        order.save()
        
        # Update delivery boy status if order is completed
        if new_status in ['DELIVERED', 'NOT_DELIVERED']:
            request.user.delivery_profile.status = 'AVAILABLE'
            request.user.delivery_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Order status updated to {new_status}'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found or not assigned to you'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
