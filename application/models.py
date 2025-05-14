from django.db import models
from django.conf import settings 

class Restaurant(models.Model):
    res_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'account.Account',  
        on_delete=models.CASCADE,  
        related_name='restaurants'
    )
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.name} (ID: {self.res_id})"


class Branch(models.Model):
    branch_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    address = models.CharField(max_length=50)
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Branch {self.branch_id} of {self.restaurant.name}"


class Category(models.Model):
    cat_id = models.AutoField(primary_key=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=50)
    display_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} (Branch {self.branch.branch_id})"


class MenuItem(models.Model):
    menu_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    name = models.CharField(max_length=50)
    photo = models.ImageField(upload_to='menu_photos/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - ${self.price}"


class RestaurantTable(models.Model):
    table_id = models.AutoField(primary_key=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='tables'
    )
    table_number = models.CharField(max_length=50)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    def __str__(self):
        return f"Table {self.table_number} (Branch {self.branch.branch_id})"


class Order(models.Model):
    order_id = models.AutoField(primary_key=True)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='orders'
    )

    user = models.ForeignKey(
        'account.Account',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='orders'
    )

    date = models.DateField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default="not_paid")
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Order {self.order_id} - {self.status}"


class OrderItem(models.Model):
    orderItem_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_items'
    )

    menu = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=50, default='not_paid')

    def __str__(self):
        return f"OrderItem {self.orderItem_id} (Order {self.order.order_id})"


class Staff(models.Model):
    staff_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'account.Account',
        on_delete=models.CASCADE,
        related_name='staff_profile',
        null=True,
        blank=True
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='staff_members',
        null=True,
        blank=True
    )
    is_staff = models.BooleanField(default=True)

    def __str__(self):
        if self.user:
            return f"Staff {self.staff_id} - {self.user.username}"
        return f"Staff {self.staff_id} (No linked user)"


class Invitation(models.Model):
    invitation_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    username = models.CharField(max_length=50)
    email = models.EmailField()
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invitation {self.invitation_id} for {self.email} ({self.status})"
