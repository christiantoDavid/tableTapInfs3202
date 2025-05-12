from django.db import models
from django.conf import settings  # if needed to reference settings
# from account.models import Account  # Assuming you have an Account model in 'account' app.

class Restaurant(models.Model):
    """
    Represents a Restaurant entity.
    If a Restaurant is deleted, all related Branches (and further child objects) will also be removed (CASCADE).
    """
    res_id = models.AutoField(primary_key=True)
    # The owner of the restaurant. When the user is deleted, we can decide the behavior.
    # on_delete=models.CASCADE means removing the Account also removes this Restaurant.
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
    """
    Represents a branch of a Restaurant.
    If the Branch is deleted, related Categories, Tables, Orders, etc. will also be removed (CASCADE).
    """
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
    """
    Represents a menu category within a specific Branch.
    If the Branch is deleted, the Category is deleted (CASCADE).
    However, if there are MenuItems referencing this Category, attempting to delete the Category alone
    will raise a ProtectedError because of on_delete=PROTECT in MenuItem -> Category.
    """
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
    """
    Represents an individual menu item.
    If the Category is deleted, this record will prevent that deletion (PROTECT),
    ensuring a Category with existing MenuItems cannot be removed unless the items are handled first.
    """
    menu_id = models.AutoField(primary_key=True)
    # If Category is deleted, PROTECT ensures the Category can't be removed if a MenuItem references it.
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    # We also keep a direct reference to Branch for convenience. If Branch is removed, we remove MenuItem as well.
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    name = models.CharField(max_length=50)
    # Example using ImageField for a menu photo. Make sure MEDIA settings are configured if used.
    photo = models.ImageField(upload_to='menu_photos/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - ${self.price}"


class RestaurantTable(models.Model):
    """
    Represents a physical table in a branch.
    If the Branch is deleted, the table is also deleted (CASCADE).
    """
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
    """
    Represents a customer's order, possibly tied to a table or a user.
    If the Branch is deleted, this order is removed (CASCADE).

    Attributes:
    - order_id (AutoField): Primary key for the Order.
    - branch (ForeignKey -> Branch): The branch where this order was placed.
    - table (ForeignKey -> RestaurantTable): The table associated with this order (can be null if table is removed).
    - user (ForeignKey -> Account): The user who placed the order (can be null if user is removed).
    - date (DateTimeField): Timestamp of when the order was created (auto_now_add).
    - total (DecimalField): The total amount for the order.
    - status (CharField): The current status of the order (e.g. "not_paid", "paid", "progress", "complete").
    """

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
    # The user who placed the order. If user is removed, we might keep the record but user=null
    user = models.ForeignKey(
        'account.Account',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='orders'
    )
    # New/updated attribute 'date'
    date = models.DateField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # E.g. "not_paid", "paid", "progress", "complete"
    status = models.CharField(max_length=50, default="not_paid")
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Order {self.order_id} - {self.status}"


class OrderItem(models.Model):
    """
    Represents each item in an Order.
    If the Order is deleted, all related OrderItems are deleted (CASCADE).
    If a MenuItem is deleted, we might also cascade or protect. Here we cascade, but can adjust if needed.
    """
    orderItem_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    # If the MenuItem is removed, do we also remove the OrderItem? Usually yes -> CASCADE
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
    """
    Represents a staff member who is associated with an Account (from account app).
    This table is newly added and does not affect existing code if no existing
    logic depends on it.
    """
    staff_id = models.AutoField(primary_key=True)
    # Link to the user (Account). If user is deleted, staff is also removed.
    user = models.ForeignKey(
        'account.Account',
        on_delete=models.CASCADE,
        related_name='staff_profile',
        null=True,
        blank=True
    )
    # Optional link to a specific Restaurant if you want staff bound to a single resto:
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='staff_members',
        null=True,
        blank=True
    )
    # A simple boolean to indicate this user is staff
    is_staff = models.BooleanField(default=True)

    def __str__(self):
        if self.user:
            return f"Staff {self.staff_id} - {self.user.username}"
        return f"Staff {self.staff_id} (No linked user)"


class Invitation(models.Model):
    """
    Represents an invitation for a user to join as staff for a Restaurant.
    An invitation is linked to a Restaurant.
    """
    invitation_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    username = models.CharField(max_length=50)  # invited user's username
    email = models.EmailField()
    status = models.CharField(max_length=50, default='pending')  # 'pending', 'accepted', or 'declined'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invitation {self.invitation_id} for {self.email} ({self.status})"
