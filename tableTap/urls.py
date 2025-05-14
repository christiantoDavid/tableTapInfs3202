from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from django.conf.urls.static import static
from django.conf import settings
from application.views import (
    dashboard_view,
    manage_branches_view, 
    delete_branch_view,
    invite_staff_ajax_view,
    get_staff_invites_ajax_view,
    remove_staff_ajax_view,
    delete_invitation_ajax_view,
    notification_list_view,
    manage_menu_items_view,
    delete_menu_item_view,
    create_category_ajax,
    delete_category_ajax,
    update_category_ajax,
    manage_orders_view,
    manage_tables_view,
    regenerate_qr_view,
    menu_view,
    delete_table_view,
    move_category_up_ajax,
    move_category_down_ajax,
    cart_view,
    remove_cart_item_view,
    cancel_cart_view,
    make_order_view,
    add_to_cart_view,
    delete_order_ajax,
    delete_order_item_ajax,
    set_item_status_ajax,
    set_order_items_status_ajax,
    )

urlpatterns = [
    path('tabletap/', include([
        path('admin/', admin.site.urls),
        path('account/', include(('account.urls', 'account'), namespace='account')),
        path('application/', include('application.urls')),
        path('', TemplateView.as_view(template_name='index.html'), name='home'),
        path('login.html', TemplateView.as_view(template_name='login.html'), name='login_html'),
        path('register.html', TemplateView.as_view(template_name='register.html'), name='register_html'),
        path('dashboard.html', dashboard_view, name='dashboard_html'),
        path('manage-branches/', manage_branches_view, name='manage_branches'),
        path('manage-branches/delete/<int:branch_id>/', delete_branch_view, name='delete_branch'),
        path('manage_branches/invite_staff_ajax/', invite_staff_ajax_view, name='invite_staff_ajax'),
        path('manage_branches/get_staff_invites_ajax/', get_staff_invites_ajax_view, name='get_staff_invites_ajax'),
        path('manage_branches/remove_staff_ajax/', remove_staff_ajax_view, name='remove_staff_ajax'),
        path('manage-branches/delete-invitation-ajax/', delete_invitation_ajax_view, name='delete_invitation_ajax'),
        path('application/notif/', notification_list_view, name='notification_page'),
        path('manage-menu-items/', manage_menu_items_view, name='manage_menu_items'),
        path('manage-menu-items/delete/<int:menu_id>/', delete_menu_item_view, name='delete_menu_item'),
        path('manage-menu-items/create-category-ajax/', create_category_ajax, name='create_category_ajax'),
        path('manage-menu-items/update-category-ajax/<int:cat_id>/', update_category_ajax, name='update_category_ajax'),
        path('manage-menu-items/delete-category-ajax/<int:cat_id>/', delete_category_ajax, name='delete_category_ajax'),
        path('category/move-up/<int:cat_id>/', move_category_up_ajax, name='move_category_up_ajax'),
        path('category/move-down/<int:cat_id>/', move_category_down_ajax, name='move_category_down_ajax'),
        path('application/manage-orders/', manage_orders_view, name='manage_orders'),
        path('make_order/', make_order_view, name='make_order'),
        path('manage_orders/ajax/delete_order/<int:order_id>/', delete_order_ajax, name='delete_order_ajax'),
        path('manage_orders/ajax/delete_item/<int:order_item_id>/', delete_order_item_ajax, name='delete_order_item_ajax'),
        path('manage_orders/ajax/set_item_status/<int:order_item_id>/', set_item_status_ajax, name='set_item_status_ajax'),
        path('manage_orders/ajax/set_all_items_status/<int:order_id>/', set_order_items_status_ajax, name='set_order_items_status_ajax'),
        path('manage-tables/', manage_tables_view, name='manage_tables'),
        path('manage-tables/regenerate-qr/<int:table_id>/', regenerate_qr_view, name='regenerate_qr'),
        path('manage-tables/delete/<int:table_id>/', delete_table_view, name='delete_table'),
        path('menu/<int:table_id>/', menu_view, name='menu_page'),
        path('menu/add/<int:menu_id>/', add_to_cart_view, name='add_to_cart'),
        path('cart/', cart_view, name='cart_page'),
        path('cart/remove/<int:menu_id>/', remove_cart_item_view, name='remove_cart_item'),
        path('cart/cancel/', cancel_cart_view, name='cancel_cart'),
        path('cart/make_order/', make_order_view, name='make_order'),
    ]))

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)