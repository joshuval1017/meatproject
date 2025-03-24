from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from products.models import Product
from django.contrib import messages
from decimal import Decimal
from .models import Cart, CartItem
from django.db import transaction

# Create your views here.

@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    context = {
        'cart_items': cart.items.select_related('product').all(),
        'cart_total': cart.total,
        'delivery_fee': 0 if cart.total >= 1000 else 50,
        'total_with_delivery': cart.total if cart.total >= 1000 else cart.total + 50,
        'has_stock_issues': cart.has_stock_issues()
    }
    return render(request, 'cart/cart.html', context)

@require_POST
@login_required
def cart_add(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id, is_available=True, is_approved=True)
        quantity = Decimal(request.POST.get('quantity', 1))
        
        # Validate minimum order quantity
        if quantity < product.minimum_order_quantity:
            return JsonResponse({
                'status': 'error',
                'message': f'Minimum order quantity is {product.minimum_order_quantity}kg'
            }, status=400)
        
        # Validate stock quantity
        if quantity > product.stock_quantity:
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.stock_quantity}kg available in stock'
            }, status=400)
        
        # Get or create cart for user
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        # Add item to cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity = quantity
            cart_item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Product added to cart',
            'cart_count': cart.items.count()
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Product not found or unavailable'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@require_POST
def cart_update(request, product_id):
    cart = request.session.get('cart', {})
    product_id = str(product_id)
    quantity = float(request.POST.get('quantity', 0))
    
    try:
        product = get_object_or_404(Product, id=int(product_id), is_available=True, is_approved=True)
        
        # Validate minimum order quantity
        if quantity > 0 and quantity < float(product.minimum_order_quantity):
            return JsonResponse({
                'status': 'error',
                'message': f'Minimum order quantity is {product.minimum_order_quantity}kg'
            }, status=400)
        
        # Validate stock quantity
        if quantity > float(product.stock_quantity):
            return JsonResponse({
                'status': 'error',
                'message': f'Only {product.stock_quantity}kg available in stock'
            }, status=400)
        
        if quantity > 0:
            cart[product_id] = quantity
        else:
            cart.pop(product_id, None)
        
        request.session['cart'] = cart
        return JsonResponse({
            'status': 'success',
            'message': 'Cart updated',
            'cart_count': sum(float(qty) for qty in cart.values())
        })
        
    except Product.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Product not found or unavailable'
        }, status=404)

@require_POST
def cart_remove(request, product_id):
    cart = request.session.get('cart', {})
    product_id = str(product_id)
    
    if product_id in cart:
        del cart[product_id]
        request.session['cart'] = cart
        
    return JsonResponse({
        'status': 'success',
        'message': 'Product removed from cart',
        'cart_count': sum(float(qty) for qty in cart.values())
    })

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = Decimal(request.POST.get('quantity', 0))
    
    # Check if product is available and has sufficient stock
    if not product.is_available:
        messages.error(request, "This product is not available for purchase.")
        return redirect('buyer_dashboard:product_detail', product_id=product_id)
        
    if quantity > product.stock_quantity:
        messages.error(request, f"Only {product.stock_quantity}kg available in stock.")
        return redirect('buyer_dashboard:product_detail', product_id=product_id)
        
    if quantity < product.minimum_order_quantity:
        messages.error(request, f"Minimum order quantity is {product.minimum_order_quantity}kg.")
        return redirect('buyer_dashboard:product_detail', product_id=product_id)

    # Get or create cart and cart item
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        # Check if updated quantity exceeds stock
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock_quantity:
            messages.error(request, f"Cannot add more. Only {product.stock_quantity}kg available in stock.")
            return redirect('buyer_dashboard:product_detail', product_id=product_id)
        cart_item.quantity = new_quantity
        cart_item.save()

    messages.success(request, f"Added {quantity}kg of {product.name} to cart.")
    return redirect('cart:view')

@login_required
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = Decimal(request.POST.get('quantity', 0))
    
    # Check stock availability
    if quantity > cart_item.product.stock_quantity:
        messages.error(request, f"Only {cart_item.product.stock_quantity}kg available in stock.")
        return redirect('cart:view')
        
    if quantity < cart_item.product.minimum_order_quantity:
        messages.error(request, f"Minimum order quantity is {cart_item.product.minimum_order_quantity}kg.")
        return redirect('cart:view')
    
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save()
    else:
        cart_item.delete()
    
    messages.success(request, "Cart updated successfully.")
    return redirect('cart:view')

@login_required
def cart_remove(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('cart:view')

@login_required
def checkout(request):
    cart = request.user.cart
    cart_items = cart.items.select_related('product').all()
    
    # Check stock availability for all items
    stock_issues = []
    for item in cart_items:
        if item.quantity > item.product.stock_quantity:
            stock_issues.append(
                f"{item.product.name}: Only {item.product.stock_quantity}kg available"
            )
    
    if stock_issues:
        messages.error(request, "Stock availability issues:\n" + "\n".join(stock_issues))
        return redirect('cart:view')
    
    # Process checkout
    # ... rest of the checkout logic ...
