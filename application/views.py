# application/views.py

import json
import jwt
from datetime import datetime, date, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages

from account.models import Account
from .models import (
    Restaurant, Order, Branch, Category, MenuItem,
    OrderItem, RestaurantTable, Staff, Invitation
)

import os
import io
import qrcode
from django.core.files.base import ContentFile
from django.db.models import Q, Max
from django.db.models.deletion import ProtectedError
from decimal import Decimal


#########################################
#               Dashboard               #
#########################################
def dashboard_view(request):
    """
    Dashboard page: 
    - Decodes JWT to find the user.
    - Filters and displays restaurants for that user (including staff).
    - Applies optional filters for orders (alltime, monthly).
    - Builds chart data for monthly line chart.
    """

    # 1) Decode JWT
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        account_id = payload.get('user_id')
    except jwt.ExpiredSignatureError:
        # messages.error(request, "Session has expired.")
        return redirect('/')
    except jwt.DecodeError:
        messages.error(request, "Invalid token.")
        return redirect('/')

    # 2) Get the Account
    try:
        account = Account.objects.get(user_id=account_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    # 3) Query all restaurants that belong to this user (owner) OR user is staff
    restaurants = Restaurant.objects.filter(
        Q(user=account) | Q(staff_members__user=account)
    ).distinct().order_by('name')

    # 4) Parse GET params
    order_filter = request.GET.get('order_filter', 'alltime')  # "alltime" or "monthly"
    selected_restaurant_id = request.GET.get('restaurant_id')

    chart_year_param = request.GET.get('chart_year')
    try:
        chart_year = int(chart_year_param)
    except (ValueError, TypeError):
        chart_year = datetime.now().year  # default fallback for chart only

    filter_year_param = request.GET.get('filter_year')
    filter_month_param = request.GET.get('filter_month')
    try:
        filter_year = int(filter_year_param)
    except (ValueError, TypeError):
        filter_year = None
    try:
        filter_month = int(filter_month_param)
    except (ValueError, TypeError):
        filter_month = None

    # 5) Determine selected restaurant
    if selected_restaurant_id:
        try:
            selected_restaurant = restaurants.get(pk=selected_restaurant_id)
        except Restaurant.DoesNotExist:
            selected_restaurant = None
    else:
        selected_restaurant = restaurants.first() if restaurants.exists() else None

    # 6) Calculate order_count and chart_data
    order_count = 0
    chart_data = [0] * 12  # monthly data from Jan to Dec
    if selected_restaurant:
        orders_queryset = Order.objects.filter(branch__restaurant=selected_restaurant)

        # a) order_count
        if order_filter == 'alltime':
            order_count = orders_queryset.count()

        elif order_filter == 'monthly':
            # Pastikan filter_year dan filter_month terbaca
            if filter_year is not None and filter_month is not None:
                order_count = orders_queryset.filter(
                    date__year=filter_year,
                    date__month=filter_month
                ).count()
            else:
                # Jika user belum memilih year/month, set 0
                order_count = 0

        # b) monthly chart data
        for month_idx in range(1, 13):
            monthly_count = orders_queryset.filter(
                date__year=chart_year,
                date__month=month_idx
            ).count()
            chart_data[month_idx - 1] = monthly_count

    # 7) Build dropdown lists
    years = list(range(2010, 2031))
    months = list(range(1, 13))

    # 8) Build context (including the user's photo URL)
    context = {
        'username': account.username,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',

        'restaurants': restaurants,
        'selected_restaurant': selected_restaurant,
        'order_filter': order_filter,
        'order_count': order_count,
        'chart_year': chart_year,
        'chart_data': json.dumps(chart_data),
        'years': years,
        'months': months,
        'filter_year': filter_year,
        'filter_month': filter_month,
    }
    return render(request, 'dashboard.html', context)


#########################################
#           Manage Branches             #
#########################################
def manage_branches_view(request):
    """
    Displays Branches for the current user.
    When updating, we rely on restaurant_id to update the existing row.
    Additionally, if the current account is the owner (restaurant.user == account),
    a "Manage Restaurant" button is displayed on the branch card.
    When clicked, a modal shows two sections:
      - Staff List: List of staff members associated with the restaurant.
      - Invitation List: List of pending invitations for that restaurant.
      Also a top section to send invitation (by username or email).
    """
    # 1) Decode JWT from session
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except jwt.ExpiredSignatureError:
        messages.error(request, "Session has expired.")
        return redirect('/')
    except jwt.DecodeError:
        messages.error(request, "Invalid token.")
        return redirect('/')

    # 2) Get Account
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    # 3) If POST => create or update branch and restaurant
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        restaurant_id = request.POST.get('restaurant_id')  # Hidden field
        restaurant_name = request.POST.get('restaurant_name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')

        # Update existing restaurant if restaurant_id provided
        if restaurant_id:
            try:
                resto = Restaurant.objects.get(res_id=restaurant_id, user=account)
                resto.name = restaurant_name
                resto.save()
            except Restaurant.DoesNotExist:
                resto = Restaurant.objects.create(user=account, name=restaurant_name)
        else:
            try:
                resto = Restaurant.objects.get(name=restaurant_name, user=account)
            except Restaurant.DoesNotExist:
                resto = Restaurant.objects.create(user=account, name=restaurant_name)

        if branch_id:
            try:
                branch = Branch.objects.get(branch_id=branch_id, restaurant__user=account)
                branch.restaurant = resto
                branch.address = address
                branch.phone = phone
                branch.save()
                messages.success(request, "Branch updated successfully.")
            except Branch.DoesNotExist:
                messages.error(request, "Branch not found or not yours.")
        else:
            Branch.objects.create(
                restaurant=resto,
                address=address,
                phone=phone
            )
            # messages.success(request, "Branch created successfully.")

        return redirect('manage_branches')

    # 4) GET request => show branches
    branches = Branch.objects.filter(
        Q(restaurant__user=account) |
        Q(restaurant__staff_members__user=account)
    ).distinct().order_by('-branch_id')

    branch_staff = {}
    branch_invites = {}
    for br in branches:
        if br.restaurant.user == account:
            staff_list = Staff.objects.filter(restaurant=br.restaurant)
            invites = Invitation.objects.filter(restaurant=br.restaurant, status='pending')
            branch_staff[br.branch_id] = staff_list
            branch_invites[br.branch_id] = invites

    context = {
        'username': account.username,
        'account': account,
        'user_email': account.email,
        'branches': branches,
        'branch_staff': branch_staff,
        'branch_invites': branch_invites,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
    }
    return render(request, 'manage-branches.html', context)


def delete_branch_view(request, branch_id):
    """
    Deletes a Branch if it belongs to the current user's Restaurant.
    Additionally, deletes the Restaurant as well so that it won't appear in filters.
    """
    # 1) Decode JWT
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except jwt.ExpiredSignatureError:
        messages.error(request, "Session has expired.")
        return redirect('/')
    except jwt.DecodeError:
        messages.error(request, "Invalid token.")
        return redirect('/')

    # 2) Get Account
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    try:
        branch = Branch.objects.get(branch_id=branch_id, restaurant__user=account)
        restaurant = branch.restaurant
        # Delete the restaurant so it is removed from all filters.
        restaurant.delete()
        # messages.success(request, "Branch and Restaurant deleted successfully.")
    except Branch.DoesNotExist:
        print("meow")
        # messages.error(request, "Branch not found or not yours.")

    return redirect('manage_branches')


@csrf_exempt
def invite_staff_ajax_view(request):
    """
    Handle AJAX POST to create a new Invitation for a restaurant.
    Returns JSON with updated/pending invitations.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)

        restaurant_id = body.get('restaurant_id')
        inviteValue = body.get('inviteValue')  # user input: email or username

        if not restaurant_id or not inviteValue:
            return JsonResponse({'success': False, 'error': 'Missing data.'}, status=400)

        # Find the restaurant
        try:
            resto = Restaurant.objects.get(res_id=restaurant_id)
        except Restaurant.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Restaurant not found.'}, status=404)

        # Create invitation
        new_invite = Invitation.objects.create(
            restaurant=resto,
            username=inviteValue,
            email=inviteValue,
            status='pending'
        )

        # Grab updated pending invites
        pending_invites = Invitation.objects.filter(restaurant=resto, status='pending')

        invites_data = []
        for inv in pending_invites:
            invites_data.append({
                'invitation_id': inv.invitation_id,
                'username': inv.username,
                'email': inv.email,
                'status': inv.status,
            })

        return JsonResponse({
            'success': True,
            'invites': invites_data
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def get_staff_invites_ajax_view(request):
    """
    Returns the current staff list and pending invitations
    for a given restaurant_id, so the Manage Restaurant modal
    can refresh its data without a full page reload.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)

        restaurant_id = body.get('restaurant_id')
        if not restaurant_id:
            return JsonResponse({'success': False, 'error': 'Missing restaurant_id.'}, status=400)

        try:
            resto = Restaurant.objects.get(res_id=restaurant_id)
        except Restaurant.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Restaurant not found.'}, status=404)

        # Staff list
        staff_qs = Staff.objects.filter(restaurant=resto)
        staff_data = []
        for s in staff_qs:
            staff_data.append({
                'staff_id': s.staff_id,
                'username': s.user.username if s.user else 'N/A',
                'email': s.user.email if s.user else 'N/A',
            })

        # Pending invites
        invites_qs = Invitation.objects.filter(restaurant=resto, status='pending')
        invites_data = []
        for inv in invites_qs:
            invites_data.append({
                'invitation_id': inv.invitation_id,
                'username': inv.username,
                'email': inv.email,
                'status': inv.status,
            })

        return JsonResponse({
            'success': True,
            'staff_list': staff_data,
            'invites_list': invites_data
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def remove_staff_ajax_view(request):
    """
    AJAX POST to remove a staff member (Staff record).
    Returns updated staff_list and invites_list for the given restaurant.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)

        staff_id = body.get('staff_id')
        restaurant_id = body.get('restaurant_id')
        if not staff_id or not restaurant_id:
            return JsonResponse({'success': False, 'error': 'Missing staff_id or restaurant_id.'}, status=400)

        # Find the staff record
        try:
            staff_obj = Staff.objects.get(
                staff_id=staff_id,
                restaurant__res_id=restaurant_id
            )
        except Staff.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Staff record not found.'}, status=404)

        # Delete the staff record
        staff_obj.delete()

        # Now return the updated staff & invites for that restaurant
        try:
            resto = Restaurant.objects.get(res_id=restaurant_id)
        except Restaurant.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Restaurant not found after removal.'}, status=404)

        # Staff list
        staff_qs = Staff.objects.filter(restaurant=resto)
        staff_data = []
        for s in staff_qs:
            staff_data.append({
                'staff_id': s.staff_id,
                'username': s.user.username if s.user else 'N/A',
                'email': s.user.email if s.user else 'N/A',
            })

        # Pending invites
        invites_qs = Invitation.objects.filter(restaurant=resto, status='pending')
        invites_data = []
        for inv in invites_qs:
            invites_data.append({
                'invitation_id': inv.invitation_id,
                'username': inv.username,
                'email': inv.email,
                'status': inv.status,
            })

        return JsonResponse({
            'success': True,
            'staff_list': staff_data,
            'invites_list': invites_data
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def delete_invitation_ajax_view(request):
    """
    Handle AJAX POST to delete a pending Invitation.
    Returns JSON with the updated list of pending invitations.
    Expected JSON body: { "invitation_id": <int>, "restaurant_id": <int> }
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)

        inv_id = body.get('invitation_id')
        rest_id = body.get('restaurant_id')

        if not inv_id or not rest_id:
            return JsonResponse({'success': False, 'error': 'Missing invitation_id or restaurant_id.'}, status=400)

        # Attempt to find the invitation
        try:
            invitation = Invitation.objects.get(
                invitation_id=inv_id,
                restaurant__res_id=rest_id,
                status='pending'
            )
        except Invitation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invitation not found or not pending.'
            }, status=404)

        # Delete the invitation (or set status='cancelled' if you prefer)
        invitation.delete()

        # Return the updated list of pending invites
        pending_invites = Invitation.objects.filter(restaurant__res_id=rest_id, status='pending')
        invites_data = []
        for inv in pending_invites:
            invites_data.append({
                'invitation_id': inv.invitation_id,
                'username': inv.username,
                'email': inv.email,
                'status': inv.status,
            })

        return JsonResponse({
            'success': True,
            'invites_list': invites_data
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


def notification_list_view(request):
    """
    Displays a list of invitations (notifications) for the current user.
    Allows user to accept or decline the invitation.
    If accepted => create Staff record, set invitation.status='accepted'.
    If declined => set invitation.status='declined'.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except jwt.ExpiredSignatureError:
        messages.error(request, "Session has expired.")
        return redirect('/')
    except jwt.DecodeError:
        messages.error(request, "Invalid token.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    if request.method == 'POST':
        invitation_id = request.POST.get('invitation_id')
        action = request.POST.get('action')  # 'accept' or 'decline'
        try:
            invitation = Invitation.objects.get(
                invitation_id=invitation_id,
                email=account.email,
                status='pending'
            )
        except Invitation.DoesNotExist:
            messages.error(request, "Invitation not found or not pending.")
            return redirect('notification_page')
        if action == 'accept':
            invitation.status = 'accepted'
            invitation.save()
            staff_exists = Staff.objects.filter(
                user=account,
                restaurant=invitation.restaurant
            ).exists()
            if not staff_exists:
                Staff.objects.create(
                    user=account,
                    restaurant=invitation.restaurant,
                    is_staff=True
                )
            # messages.success(request, f"You have accepted invitation to {invitation.restaurant.name}.")
            return redirect('notification_page')
        elif action == 'decline':
            invitation.status = 'declined'
            invitation.save()
            # messages.info(request, f"You have declined invitation to {invitation.restaurant.name}.")
        else:
            messages.error(request, "Unknown action.")
        return redirect('notification_page')
    invitations = Invitation.objects.filter(email=account.email, status='pending')
    context = {
        'username': account.username,
        'invitations': invitations,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
    }
    return render(request, 'notif.html', context)


#########################################
#       Manage Menu Items View          #
#########################################
def manage_menu_items_view(request):
    """
    Displays and manages Menu Items:
    - Filter by restaurant_id and category_id.
    - Show categories in the correct display_order.
    - Create/Update MenuItems on POST.
    - If '?edit=<menu_id>' is present, open Edit Modal.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid or expired.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    user_restaurants = Restaurant.objects.filter(
        Q(user=account) | Q(staff_members__user=account)
    ).distinct().order_by('name')
    restaurant_id = request.GET.get('restaurant_id')
    cat_id = request.GET.get('cat_id')
    edit_menu_id = request.GET.get('edit')
    if restaurant_id:
        try:
            selected_restaurant = user_restaurants.get(res_id=restaurant_id)
        except Restaurant.DoesNotExist:
            selected_restaurant = None
    else:
        selected_restaurant = user_restaurants.first() if user_restaurants.exists() else None
    categories = []
    menu_items = []
    menu_item_description_map = {}
    selected_category = None
    editing_item = None
    if selected_restaurant:
        branches = Branch.objects.filter(restaurant=selected_restaurant)
        categories = Category.objects.filter(branch__in=branches).order_by('display_order')
        menu_items = MenuItem.objects.filter(branch__in=branches).order_by('name')
        if cat_id:
            try:
                selected_category = categories.get(cat_id=cat_id)
                menu_items = menu_items.filter(category=selected_category)
            except Category.DoesNotExist:
                selected_category = None
        if edit_menu_id:
            try:
                editing_item = menu_items.get(menu_id=edit_menu_id)
            except MenuItem.DoesNotExist:
                editing_item = None
        for mi in menu_items:
            menu_item_description_map[mi.menu_id] = f"Description or additional info..."
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_menu_item':
            name = request.POST.get('name')
            price = request.POST.get('price')
            cat_id_form = request.POST.get('category_id')
            desc = request.POST.get('description', '')
            photo_file = request.FILES.get('photo')
            if not selected_restaurant:
                messages.error(request, "No restaurant selected.")
                return redirect('manage_menu_items')
            branch = Branch.objects.filter(restaurant=selected_restaurant).first()
            if not branch:
                messages.error(request, "No branch found for the selected restaurant.")
                return redirect('manage_menu_items')
            try:
                category_obj = Category.objects.get(
                    cat_id=cat_id_form, 
                    branch__in=Branch.objects.filter(restaurant=selected_restaurant)
                )
            except Category.DoesNotExist:
                messages.error(request, "Category does not exist in this restaurant.")
                return redirect('manage_menu_items')
            new_item = MenuItem.objects.create(
                category=category_obj,
                branch=branch,
                name=name,
                price=price,
                description=desc,
            )
            if photo_file:
                new_item.photo = photo_file
                new_item.save()
            # messages.success(request, "Menu item created successfully.")
            return redirect('manage_menu_items')
        elif action == 'update_menu_item':
            menu_id_form = request.POST.get('menu_id')
            name = request.POST.get('name')
            price = request.POST.get('price')
            cat_id_form = request.POST.get('category_id')
            desc = request.POST.get('description', '')
            photo_file = request.FILES.get('photo')
            try:
                item_to_update = MenuItem.objects.get(
                    menu_id=menu_id_form, 
                    branch__restaurant__user=account
                )
            except MenuItem.DoesNotExist:
                messages.error(request, "Menu item not found or not yours.")
                return redirect('manage_menu_items')
            try:
                category_obj = Category.objects.get(
                    cat_id=cat_id_form, 
                    branch__in=Branch.objects.filter(restaurant=item_to_update.branch.restaurant)
                )
            except Category.DoesNotExist:
                messages.error(request, "Category does not exist in this restaurant.")
                return redirect('manage_menu_items')
            item_to_update.name = name
            item_to_update.price = price
            item_to_update.category = category_obj
            item_to_update.description = desc
            if photo_file:
                item_to_update.photo = photo_file
            item_to_update.save()
            messages.success(request, "Menu item updated successfully.")
            return redirect('manage_menu_items')
    context = {
        'username': account.username,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
        'user_restaurants': user_restaurants,
        'selected_restaurant': selected_restaurant,
        'categories': categories,
        'selected_category': selected_category,
        'menu_items': menu_items,
        'menu_item_description_map': {'menu_item': menu_item_description_map},
        'editing_item': editing_item,
    }
    return render(request, 'manage-menu-items.html', context)


#########################################
#           Delete Menu Item            #
#########################################
def delete_menu_item_view(request, menu_id):
    """
    Deletes a MenuItem if it belongs to the current user's restaurant.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session expired or invalid.")
        return redirect('/')

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    try:
        menu_item = MenuItem.objects.get(menu_id=menu_id, branch__restaurant__user=account)
        menu_item.delete()
        # messages.success(request, "Menu item deleted.")
    except MenuItem.DoesNotExist:
        messages.error(request, "Menu item not found or not yours.")

    return redirect('manage_menu_items')


#########################################
#  Create, Update, Delete Category AJAX #
#########################################
@csrf_exempt
def create_category_ajax(request):
    """
    Creates a new category with a proper display_order (max + 1).
    Returns JSON: { success: true, cat_id: ..., name: ... }
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        token = request.session.get('jwt_token')
        if not token:
            return JsonResponse({'success': False, 'error': 'Not logged in.'})
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
        except:
            return JsonResponse({'success': False, 'error': 'Invalid or expired token.'})

        try:
            account = Account.objects.get(user_id=user_id)
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Account not found.'})

        # Parse JSON body
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'})

        cat_name = body.get('name')
        rest_id = body.get('restaurant_id')
        if not cat_name:
            return JsonResponse({'success': False, 'error': 'No category name provided.'})
        if not rest_id:
            return JsonResponse({'success': False, 'error': 'No restaurant_id provided.'})

        # Find the chosen restaurant
        try:
            restaurant = Restaurant.objects.get(
                Q(user=account) | Q(staff_members__user=account),
                res_id=rest_id
            )
        except Restaurant.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Restaurant not found or not yours.'})

        branch = Branch.objects.filter(restaurant=restaurant).first()
        if not branch:
            return JsonResponse({'success': False, 'error': 'No branch to assign category.'})

        # Determine the max display_order so far for this branch
        last_order = Category.objects.filter(branch=branch).aggregate(max_order=Max('display_order'))['max_order']
        if last_order is None:
            last_order = 0

        # Create the category with display_order = max + 1
        new_cat = Category.objects.create(
            branch=branch,
            name=cat_name,
            display_order=last_order + 1
        )
        return JsonResponse({
            'success': True,
            'cat_id': new_cat.cat_id,
            'name': new_cat.name
        })
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method or not AJAX.'})


@csrf_exempt
def update_category_ajax(request, cat_id):
    """
    Updates an existing category name. 
    Returns JSON: { success: true, name: ... } or { success: false, error: ... }
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        token = request.session.get('jwt_token')
        if not token:
            return JsonResponse({'success': False, 'error': 'Not logged in.'})
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
        except:
            return JsonResponse({'success': False, 'error': 'Invalid or expired token.'})

        try:
            account = Account.objects.get(user_id=user_id)
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Account not found.'})

        # Parse JSON
        try:
            body = json.loads(request.body)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'})

        new_name = body.get('name')
        rest_id = body.get('restaurant_id')
        if not new_name:
            return JsonResponse({'success': False, 'error': 'No new category name provided.'})
        if not rest_id:
            return JsonResponse({'success': False, 'error': 'No restaurant_id provided.'})

        # Validate the restaurant (owner or staff)
        try:
            restaurant = Restaurant.objects.get(
                Q(user=account) | Q(staff_members__user=account),
                res_id=rest_id
            )
        except Restaurant.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Restaurant not found or not yours.'})

        # Attempt to update the category if it belongs to that restaurant
        try:
            category = Category.objects.get(
                cat_id=cat_id,
                branch__restaurant=restaurant
            )
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found or not yours.'})

        category.name = new_name
        category.save()

        return JsonResponse({
            'success': True,
            'name': category.name
        })
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def delete_category_ajax(request, cat_id):
    """
    Deletes a category if it belongs to the user or staff,
    but only if no MenuItems reference it.
    Returns JSON: { success: true } or { success: false, error: ... }
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        token = request.session.get('jwt_token')
        if not token:
            return JsonResponse({'success': False, 'error': 'Not logged in.'})
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user_id = payload.get('user_id')
        except:
            return JsonResponse({'success': False, 'error': 'Invalid or expired token.'})

        try:
            account = Account.objects.get(user_id=user_id)
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Account not found.'})

        try:
            # Ensure category is from a restaurant where user is owner or staff
            category = Category.objects.get(
                cat_id=cat_id,
                branch__restaurant__in=Restaurant.objects.filter(
                    Q(user=account) | Q(staff_members__user=account)
                )
            )

            from .models import MenuItem
            if MenuItem.objects.filter(category=category).exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Cannot delete category with existing MenuItems.'
                })

            category.delete()
            return JsonResponse({'success': True})

        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found or not yours.'})
        except ProtectedError:
            return JsonResponse({'success': False, 'error': 'Cannot delete category with existing references.'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def move_category_up_ajax(request, cat_id):
    """
    Moves the specified category up by swapping its display_order with the previous category.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            category = Category.objects.get(cat_id=cat_id)
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found.'})
        
        # Find the category with display_order just below this one
        previous_cat = Category.objects.filter(
            branch=category.branch,
            display_order__lt=category.display_order
        ).order_by('-display_order').first()
        
        if previous_cat:
            category.display_order, previous_cat.display_order = previous_cat.display_order, category.display_order
            category.save()
            previous_cat.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'No previous category found.'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request or not AJAX.'})


@csrf_exempt
def move_category_down_ajax(request, cat_id):
    """
    Moves the specified category down by swapping its display_order with the next category.
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            category = Category.objects.get(cat_id=cat_id)
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found.'})

        # Find the category with display_order just above this one
        next_cat = Category.objects.filter(
            branch=category.branch,
            display_order__gt=category.display_order
        ).order_by('display_order').first()

        if next_cat:
            category.display_order, next_cat.display_order = next_cat.display_order, category.display_order
            category.save()
            next_cat.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'No next category found.'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request or not AJAX.'})


#########################################
#           manage-orders               #
#########################################
def manage_orders_view(request):
    """
    Displays orders for the current user's restaurants.
    If ?ajax=1, we render the same template but set ajax_mode=True, so only partial markup is returned.
    Otherwise, we render the full layout with ajax_mode=False.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid.")
        return redirect('/')

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    # Tampilkan restoran di mana user adalah owner atau staff
    user_restaurants = Restaurant.objects.filter(
        Q(user=account) | Q(staff_members__user=account)
    ).distinct().order_by('name')

    restaurant_id = request.GET.get('restaurant_id', '')
    date_str = request.GET.get('date', '')

    # Jika user belum memilih tanggal, default = hari ini
    if not date_str:
        date_str = date.today().isoformat()

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        selected_date = date.today()

    orders_queryset = Order.objects.none()
    selected_restaurant = None

    # Jika user memilih restaurant tertentu (bukan 'all')
    if restaurant_id and restaurant_id.lower() != 'all':
        try:
            selected_restaurant = user_restaurants.get(res_id=restaurant_id)
            # Contoh filter by exact date
            # Jika nanti ingin mingguan, jangan pakai __date, cukup date__gte / date__lte
            orders_queryset = Order.objects.filter(
                branch__restaurant=selected_restaurant,
                date=selected_date
            ).order_by('-order_id')
        except Restaurant.DoesNotExist:
            selected_restaurant = None

    # Tambahkan photo profile ke context agar base1.html bisa menampilkan
    user_photo_url = account.photo_profile.url if account.photo_profile else '/static/user.png'

    context = {
        'username': account.username,
        'user_email': account.email,
        'user_restaurants': user_restaurants,
        'selected_restaurant': selected_restaurant,
        'selected_date': selected_date,
        'restaurant_id': restaurant_id if (restaurant_id and restaurant_id.lower() != 'all') else 'all',
        'orders': orders_queryset,
        'ajax_mode': (request.GET.get('ajax') == '1'),

        # Inilah kuncinya agar base1.html dapat menampilkan foto user
        'user_photo_url': user_photo_url,
    }

    return render(request, 'manage-orders.html', context)


# ---------- AJAX VIEWS FOR manage_orders (no full page reload) ----------
@csrf_exempt
def delete_order_ajax(request, order_id):
    """
    Deletes the entire Order if it belongs to the user's branch, returns JSON.
    """
    token = request.session.get('jwt_token')
    if not token:
        return JsonResponse({"error": "Not logged in."}, status=403)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except:
        return JsonResponse({"error": "Invalid token."}, status=403)

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        return JsonResponse({"error": "Account not found."}, status=403)

    try:
        order = Order.objects.get(order_id=order_id, branch__restaurant__user=account)
        order.delete()
        return JsonResponse({"success": True, "message": "Order deleted."})
    except Order.DoesNotExist:
        return JsonResponse({"success": False, "message": "Order not found or not yours."}, status=404)


@csrf_exempt
def delete_order_item_ajax(request, order_item_id):
    """
    Deletes a single item from an Order if it belongs to the user's branch, returns JSON.
    """
    token = request.session.get('jwt_token')
    if not token:
        return JsonResponse({"error": "Not logged in."}, status=403)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except:
        return JsonResponse({"error": "Invalid token."}, status=403)

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        return JsonResponse({"error": "Account not found."}, status=403)

    try:
        item = OrderItem.objects.get(
            orderItem_id=order_item_id,
            order__branch__restaurant__user=account
        )
        item.delete()
        return JsonResponse({"success": True, "message": "Order item deleted."})
    except OrderItem.DoesNotExist:
        return JsonResponse({"success": False, "message": "Item not found or not yours."}, status=404)


@csrf_exempt
def set_item_status_ajax(request, order_item_id):
    """
    Updates the status of a single OrderItem (e.g. 'not_paid', 'progress', 'complete'), returns JSON.
    Expects POST with 'new_status'.
    """
    token = request.session.get('jwt_token')
    if not token:
        return JsonResponse({"error": "Not logged in."}, status=403)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except:
        return JsonResponse({"error": "Invalid token."}, status=403)

    new_status = request.POST.get('new_status', '')

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        return JsonResponse({"error": "Account not found."}, status=403)

    try:
        item = OrderItem.objects.get(
            orderItem_id=order_item_id,
            order__branch__restaurant__user=account
        )
        item.status = new_status
        item.save()
        return JsonResponse({
            "success": True,
            "message": f"Item status updated to {new_status}.",
            "new_status": new_status
        })
    except OrderItem.DoesNotExist:
        return JsonResponse({"success": False, "message": "Item not found or not yours."}, status=404)


@csrf_exempt
def set_order_items_status_ajax(request, order_id):
    """
    Updates the status of ALL items in an order to the specified new_status, returns JSON.
    Expects POST with 'new_status'.
    """
    token = request.session.get('jwt_token')
    if not token:
        return JsonResponse({"error": "Not logged in."}, status=403)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except:
        return JsonResponse({"error": "Invalid token."}, status=403)

    new_status = request.POST.get('new_status', '')

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        return JsonResponse({"error": "Account not found."}, status=403)

    try:
        order = Order.objects.get(order_id=order_id, branch__restaurant__user=account)
        for item in order.order_items.all():
            item.status = new_status
            item.save()
        return JsonResponse({
            "success": True,
            "message": f"All items in Order {order_id} updated to {new_status}.",
            "new_status": new_status
        })
    except Order.DoesNotExist:
        return JsonResponse({"success": False, "message": "Order not found or not yours."}, status=404)


#########################################
#           manage-tables               #
#########################################
def manage_tables_view(request):
    """
    Show tables for the selected restaurant.
    If user POSTs 'create_table', we read 'restaurant_id' from POST and create the table.
    Now filters restaurants by the user (owner) or staff.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    user_restaurants = Restaurant.objects.filter(
        Q(user=account) | Q(staff_members__user=account)
    ).distinct().order_by('name')
    restaurant_id = request.GET.get('restaurant_id')
    selected_restaurant = None
    if restaurant_id:
        try:
            selected_restaurant = user_restaurants.get(res_id=int(restaurant_id))
        except (Restaurant.DoesNotExist, ValueError):
            selected_restaurant = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_table':
            table_number = request.POST.get('table_number', '').strip()
            post_rest_id = request.POST.get('restaurant_id', '').strip()
            if not post_rest_id:
                messages.error(request, "Please select a valid restaurant before creating a table.")
                return redirect('manage_tables')
            try:
                chosen_restaurant = user_restaurants.get(res_id=int(post_rest_id))
            except (Restaurant.DoesNotExist, ValueError):
                messages.error(request, "Invalid restaurant selected.")
                return redirect('manage_tables')
            branch = Branch.objects.filter(restaurant=chosen_restaurant).first()
            if not branch:
                messages.error(request, "No branch found for this restaurant.")
                return redirect('manage_tables')
            new_table = RestaurantTable.objects.create(
                branch=branch,
                table_number=table_number
            )
            qr_url = request.build_absolute_uri(f"/application/menu/{new_table.table_id}/")
            qr_img = qrcode.make(qr_url)
            buffer = io.BytesIO()
            qr_img.save(buffer, format='PNG')
            file_name = f"qr_table_{new_table.table_id}.png"
            new_table.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=True)
            # messages.success(request, f"Table '{table_number}' created successfully!")
            return redirect(f"{request.path}?restaurant_id={post_rest_id}")
    tables = []
    if selected_restaurant:
        branches = Branch.objects.filter(restaurant=selected_restaurant)
        tables = RestaurantTable.objects.filter(branch__in=branches).order_by('table_id')
    context = {
        'user_restaurants': user_restaurants,
        'selected_restaurant': selected_restaurant,
        'tables': tables,
        'username': account.username,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
    }
    return render(request, 'manage-table.html', context)


def regenerate_qr_view(request, table_id):
    """
    Regenerate the QR code for an existing table.
    """
    from django.urls import reverse

    try:
        tbl = RestaurantTable.objects.get(table_id=table_id)
    except RestaurantTable.DoesNotExist:
        messages.error(request, "Table not found.")
        return redirect('manage_tables')

    # Generate new QR
    qr_url = request.build_absolute_uri(f"/application/menu/{table_id}/")
    qr_img = qrcode.make(qr_url)
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    file_name = f"qr_table_{table_id}.png"
    tbl.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=True)

    # messages.success(request, f"QR code for table '{tbl.table_number}' regenerated.")

    restaurant_id = request.GET.get('restaurant_id')
    redirect_url = reverse('manage_tables')
    if restaurant_id:
        redirect_url += f"?restaurant_id={restaurant_id}"

    return redirect(redirect_url)


def delete_table_view(request, table_id):
    """
    Delete a table by its ID, ensuring it belongs to the user's restaurant if needed.
    """
    from django.urls import reverse
    try:
        tbl = RestaurantTable.objects.get(table_id=table_id)
        tbl.delete()
        # messages.success(request, "Table deleted successfully!")
    except RestaurantTable.DoesNotExist:
        messages.error(request, "Table not found.")

    restaurant_id = request.GET.get('restaurant_id')
    redirect_url = reverse('manage_tables')
    if restaurant_id:
        redirect_url += f"?restaurant_id={restaurant_id}"

    return redirect(redirect_url)


#########################################
#                Menu View              #
#########################################
def menu_view(request, table_id):
    """
    Displays the menu for a specific table_id.
    1) Tries to fetch the RestaurantTable. If invalid, returns an empty menu.
    2) Stores table_id in session so add_to_cart_view can redirect back.
    3) Optionally filters MenuItems by ?cat_id=...
    4) Calculates cart_count from session cart (sum of all items).
    5) Renders menu.html without touching local storage; that's handled in JS.
    """
    try:
        table_obj = RestaurantTable.objects.get(table_id=table_id)
    except RestaurantTable.DoesNotExist:
        return render(request, 'menu.html', {
            'restaurant_name': 'Unknown Restaurant',
            'table_number': '???',
            'categories': [],
            'menu_items': [],
            'cart_count': 0,
        })

    request.session['table_id'] = table_id

    restaurant = table_obj.branch.restaurant
    restaurant_name = restaurant.name
    table_number = table_obj.table_number

    cat_id = request.GET.get('cat_id')
    branches = Branch.objects.filter(restaurant=restaurant)
    categories = Category.objects.filter(branch__in=branches).distinct().order_by('name')
    menu_items = MenuItem.objects.filter(branch__in=branches).order_by('name')

    selected_category = None
    if cat_id:
        try:
            selected_category = categories.get(cat_id=cat_id)
            menu_items = menu_items.filter(category=selected_category)
        except Category.DoesNotExist:
            selected_category = None

    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())

    context = {
        'restaurant_name': restaurant_name,
        'table_number': table_number,
        'categories': categories,
        'selected_category': selected_category,
        'menu_items': menu_items,
        'cart_count': cart_count,
    }
    return render(request, 'menu.html', context)


def add_to_cart_view(request, menu_id):
    """
    Adds an item (menu_id) to the session cart with quantity from ?qty=...
    Then redirects back to menu/<table_id>.
    """
    cart = request.session.get('cart', {})
    qty_str = request.GET.get('qty')
    if qty_str:
        try:
            qty = int(qty_str)
        except ValueError:
            qty = 1
    else:
        qty = 1

    current_count = cart.get(str(menu_id), 0)
    cart[str(menu_id)] = current_count + qty
    request.session['cart'] = cart

    table_id = request.session.get('table_id')
    if not table_id:
        return redirect('cart_page')  # fallback if table_id is missing
    return redirect('menu_page', table_id=table_id)


def cart_view(request):
    """
    Displays the cart page, showing items from session cart => { menu_id: quantity }.
    Also fetches the table name and table_id so we can display them in cart.html.
    """
    cart = request.session.get('cart', {})
    cart_items = []
    total = Decimal('0.00')

    for menu_id_str, qty in cart.items():
        try:
            menu_item = MenuItem.objects.get(menu_id=int(menu_id_str))
            subtotal = menu_item.price * qty
            total += subtotal
            cart_items.append({
                'menu_id': menu_item.menu_id,
                'name': menu_item.name,
                'price': menu_item.price,
                'quantity': qty,
                'subtotal': subtotal,
            })
        except MenuItem.DoesNotExist:
            continue

    table_id = request.session.get('table_id', 0)
    table_name = "Unknown"
    if table_id:
        try:
            t_obj = RestaurantTable.objects.get(table_id=table_id)
            table_name = t_obj.table_number
        except RestaurantTable.DoesNotExist:
            pass

    context = {
        'cart_items': cart_items,
        'total': total,
        'table_name': table_name,
        'table_id': table_id,
    }
    return render(request, 'cart.html', context)


def remove_cart_item_view(request, menu_id):
    """
    Removes a single item (menu_id) from the session cart, then redirect to cart page.
    """
    cart = request.session.get('cart', {})
    if str(menu_id) in cart:
        del cart[str(menu_id)]
        request.session['cart'] = cart
        messages.success(request, "Item removed from cart.")
    return redirect('cart_page')


def cancel_cart_view(request):
    """
    Clears the entire cart + table_id from session, then redirects back to menu/<table_id>.
    """
    if 'cart' in request.session:
        del request.session['cart']
    table_id = request.session.get('table_id')
    if table_id:
        del request.session['table_id']
        messages.info(request, "Cart cancelled.")
        return redirect('menu_page', table_id=table_id)
    else:
        return redirect('cart_page')


@csrf_exempt
def make_order_view(request):
    """
    Creates an Order and OrderItems from the session cart.
    Also saves 'notes' if provided (via POST 'notes').
    Returns JSON if AJAX, otherwise redirects.
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in to place an order.")
        return redirect('/')

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid.")
        return redirect('/')

    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "Cart is empty.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"error": "Cart empty"}, status=400)
        return redirect('cart_page')

    table_id = request.session.get('table_id')
    table_obj = None
    if table_id:
        try:
            table_obj = RestaurantTable.objects.get(table_id=table_id)
        except RestaurantTable.DoesNotExist:
            table_obj = None

    if table_obj:
        branch = table_obj.branch
    else:
        # fallback
        resto = Restaurant.objects.filter(user=account).first()
        branch = Branch.objects.filter(restaurant=resto).first() if resto else None

    if not branch:
        messages.error(request, "No branch available to place an order.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"error": "No branch"}, status=400)
        return redirect('cart_page')

    # Create Order
    order = Order.objects.create(
        branch=branch,
        table=table_obj,
        user=account,
        total=Decimal('0.00'),
        status='not_paid'
    )

    order_total = Decimal('0.00')
    for menu_id_str, qty in cart.items():
        try:
            menu_item = MenuItem.objects.get(menu_id=int(menu_id_str))
            subtotal = menu_item.price * qty
            order_total += subtotal
            OrderItem.objects.create(
                order=order,
                menu=menu_item,
                quantity=qty,
                status='not_paid'
            )
        except MenuItem.DoesNotExist:
            continue

    # If notes provided
    if request.method == 'POST':
        notes_text = request.POST.get('notes', '')
        order.notes = notes_text.strip()

    order.total = order_total
    order.save()

    # Clear cart
    del request.session['cart']
    messages.success(request, "Order placed successfully!")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "message": "Order placed successfully!",
            "order_id": order.order_id
        }, status=200)

    return redirect('cart_page')

def faq_view(request):
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    context = {
        'username': account.username,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
    }
    return render(request, 'faq1.html', context)

def help_view(request):
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    context = {
        'username': account.username,
        'user_email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
    }
    return render(request, 'help1.html', context)

def set_up_profile_view(request):
    """
    Renders the page for setting up/updating the user profile.
    This page includes two forms:
      1) A form for updating username, email, and optional password
      2) A form for uploading a new profile photo
    """
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid or expired.")
        return redirect('/')
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')
    context = {
        'username': account.username,
        'email': account.email,
        'user_photo_url': account.photo_profile.url if account.photo_profile else '/static/user.png',
        'photo_url': account.photo_profile.url if account.photo_profile else '',
    }
    return render(request, 'setUpProfile.html', context)



def update_profile_view(request):
    """
    Handles partial updates to the user's profile information (username, email, optional password).
    If password is left blank, we keep the old password.
    """
    # Only allow POST
    if request.method != 'POST':
        return redirect('setUpProfile_page')

    # 1) Check user session
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid or expired.")
        return redirect('/')

    # 2) Get the Account
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    # 3) Extract form fields (partial)
    new_username = request.POST.get('username', '').strip()
    new_email = request.POST.get('email', '').strip()
    new_password = request.POST.get('password', '').strip()

    # 4) Update only if provided (partial logic)
    if new_username:
        account.username = new_username
    if new_email:
        account.email = new_email
    if new_password:
        # In a real system, you'd hash the password. Example: account.set_password(new_password)
        # For demonstration, let's just store raw (NOT recommended in production).
        account.password = new_password

    account.save()
    messages.success(request, "Profile information updated successfully.")

    return redirect('setUpProfile_page')


def update_profile_photo_view(request):
    """
    Handles only the profile photo upload. 
    Allows partial update: user can upload a photo without re-entering password or other fields.
    """
    if request.method != 'POST':
        return redirect('setUpProfile_page')

    # 1) Check session
    token = request.session.get('jwt_token')
    if not token:
        messages.error(request, "You must be logged in.")
        return redirect('/')

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        messages.error(request, "Session invalid or expired.")
        return redirect('/')

    # 2) Get the Account
    try:
        account = Account.objects.get(user_id=user_id)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect('/')

    # 3) Check if a file was uploaded
    photo_file = request.FILES.get('photo_profile')
    if photo_file:
        account.photo_profile = photo_file
        account.save()

    return redirect('setUpProfile_page')