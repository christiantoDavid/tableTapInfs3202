from django.contrib import admin
from .models import (
    Restaurant, Branch, Category, MenuItem,
    RestaurantTable, Order, OrderItem, Staff, Invitation
)

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'user')
    search_fields = ('name', 'user__username', 'user__email')

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display  = ('branch_id', 'restaurant', 'address')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'branch', 'display_order')

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display  = ('name', 'branch', 'category', 'price')
    list_filter   = ('branch', 'category')

@admin.register(RestaurantTable)
class TableAdmin(admin.ModelAdmin):
    list_display  = ('table_number', 'branch')
    list_filter   = ('branch',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ('order_id', 'branch', 'table', 'user', 'date', 'total', 'status')
    list_filter   = ('status','date')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display  = ('orderItem_id', 'order', 'menu', 'quantity', 'status')
    list_filter   = ('status',)

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display  = ('staff_id', 'user', 'restaurant', 'is_staff')

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display  = ('invitation_id', 'restaurant', 'email', 'status', 'created_at')
    list_filter   = ('status',)
