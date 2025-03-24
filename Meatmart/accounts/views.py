from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.views import (
    PasswordResetView, 
    PasswordResetDoneView,
    PasswordResetConfirmView, 
    PasswordResetCompleteView
)
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.decorators.csrf import csrf_protect
from .models import User, SellerProfile, BuyerProfile
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    UserUpdateForm,
    SellerRegistrationForm,
    SellerProfileUpdateForm,
    BuyerProfileUpdateForm
)
from django.utils.text import slugify
import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from orders.models import Address

def generate_unique_username(email):
    """Generate a unique username from email."""
    # Get the part before @ in email
    username = email.split('@')[0]
    # Slugify to make it URL friendly
    username = slugify(username)
    # Add random string to make it unique
    username = f"{username}-{str(uuid.uuid4())[:8]}"
    return username

@csrf_protect
def login_view(request):
    """Handle user login with email and password."""
    if request.user.is_authenticated:
        if request.user.role == User.Role.ADMIN:
            return redirect('admin_dashboard:dashboard')
        elif request.user.role == User.Role.SELLER:
            return redirect('seller:dashboard')
        elif request.user.role == User.Role.DELIVERY_BOY:
            return redirect('delivery:dashboard')
        else:
            return redirect('buyer:dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if email and password:
            try:
                user = User.objects.get(email=email)
                if user is not None:
                    user = authenticate(request, username=email, password=password)
                    if user is not None:
                        login(request, user)
                        messages.success(request, f'Welcome back, {user.get_full_name() or user.email}!')
                        
                        # Redirect based on user role
                        if user.role == User.Role.ADMIN:
                            return redirect('admin_dashboard:dashboard')
                        elif user.role == User.Role.SELLER:
                            return redirect('seller:dashboard')
                        elif user.role == User.Role.DELIVERY_BOY:
                            return redirect('delivery:dashboard')
                        else:
                            return redirect('buyer:dashboard')
                    else:
                        messages.error(request, 'Invalid password.')
                else:
                    messages.error(request, 'User not found.')
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email.')
        else:
            messages.error(request, 'Please enter both email and password.')
    
    return render(request, 'accounts/login.html')

@csrf_protect
def register_view(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect('shop:home')
        
    if request.method == 'POST':
        account_type = request.POST.get('account_type')
        
        if account_type == 'seller':
            form = SellerRegistrationForm(request.POST, request.FILES)
            account_name = "Seller"
        else:
            form = UserRegistrationForm(request.POST)
            account_name = "Buyer"
            
        if form.is_valid():
            user = form.save(commit=False)
            # Generate unique username from email
            user.username = generate_unique_username(form.cleaned_data['email'])
            
            if account_type == 'seller':
                user.role = User.Role.SELLER
                user.company_name = form.cleaned_data['company_name']
                user.gst_number = form.cleaned_data['gst_number']
                user.save()
                
                # Create seller profile
                SellerProfile.objects.create(
                    user=user,
                    business_license=form.cleaned_data.get('business_license'),
                )
            else:
                user.role = User.Role.BUYER
                user.save()
                
                # Create buyer profile with default values
                BuyerProfile.objects.create(
                    user=user,
                    business_type='OTHER',  # Default value
                    preferred_payment_method='BANK_TRANSFER',  # Default value
                )
            
            # Log in the user with the ModelBackend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            messages.success(
                request, 
                f'Welcome to meatmart! Your {account_name} account has been created successfully.'
            )
            
            if user.is_seller:
                return redirect('seller:dashboard')
            else:
                return redirect('shop:home')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('account_login')

class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    """Custom password reset view."""
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')
    success_message = "We've emailed you instructions for setting your password."

class CustomPasswordResetDoneView(PasswordResetDoneView):
    """Custom password reset done view."""
    template_name = 'accounts/password_reset_done.html'

class CustomPasswordResetConfirmView(SuccessMessageMixin, PasswordResetConfirmView):
    """Custom password reset confirm view."""
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    success_message = "Your password has been set successfully!"

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """Custom password reset complete view."""
    template_name = 'accounts/password_reset_complete.html'

@login_required
def profile_view(request):
    """Display and update user profile."""
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        
        if request.user.role == User.Role.SELLER:
            profile_form = SellerProfileUpdateForm(
                request.POST, 
                request.FILES, 
                instance=request.user.seller_profile
            )
        elif request.user.role == User.Role.DELIVERY_BOY:
            # Redirect delivery boys to their specific profile page
            return redirect('delivery:profile')
        else:
            profile_form = BuyerProfileUpdateForm(
                request.POST,
                instance=request.user.buyer_profile
            )
            
        if user_form.is_valid() and profile_form.is_valid():
            # Save user form with profile picture
            user = user_form.save(commit=False)
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
            user.save()
            
            # Save profile form
            profile_form.save()
            
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        if request.user.role == User.Role.DELIVERY_BOY:
            # Redirect delivery boys to their specific profile page
            return redirect('delivery:profile')
            
        user_form = UserUpdateForm(instance=request.user)
        if request.user.role == User.Role.SELLER:
            profile_form = SellerProfileUpdateForm(instance=request.user.seller_profile)
        else:
            profile_form = BuyerProfileUpdateForm(instance=request.user.buyer_profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def add_address(request):
    if request.method == 'POST':
        # Get form data
        label = request.POST.get('label')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address_line1 = request.POST.get('address_line1')
        address_line2 = request.POST.get('address_line2', '')
        city = request.POST.get('city')
        state = request.POST.get('state')
        pincode = request.POST.get('pincode')
        is_default = request.POST.get('is_default') == 'on'

        # Create new address
        address = Address.objects.create(
            user=request.user,
            label=label,
            name=name,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            pincode=pincode,
            is_default=is_default
        )

        messages.success(request, 'Address added successfully!')
        
        # Redirect back to the referring page if available
        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('accounts:profile')

    return render(request, 'accounts/add_address.html')

# Social Authentication Views
def google_login(request):
    """Handle Google OAuth login."""
    pass  # Implement Google OAuth logic

def facebook_login(request):
    """Handle Facebook OAuth login."""
    pass  # Implement Facebook OAuth logic

def apple_login(request):
    """Handle Apple OAuth login."""
    pass  # Implement Apple OAuth logic
