from django.urls import path
from . import views
from .views import mark_all_notifications_read

from .views import clear_notifications


urlpatterns = [
    path('', views.index, name='index'),

    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),

    path('games/', views.games_list, name='games'),
    path('rent/', views.rent, name='rent'),
    path('shop/', views.shop, name='shop'),

    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    path('games/join/<int:game_id>/', views.join_match, name='join_match'),
    path('leave-match/<int:game_id>/', views.leave_match, name='leave_match'),
    path('delete-match/<int:game_id>/', views.delete_match, name='delete_match'),
    path("rent/book/<int:item_id>/", views.book_item, name="book_item"),

    path('profile/my-matches/', views.my_matches, name='my_matches'),
    path('cart/', views.cart, name='cart'),
    path('profile/update-avatar/', views.update_avatar, name='update_avatar'),

    # ⭐ ВОТ ЭТО — главное
    path('become-organizer/', views.become_organizer, name='become_organizer'),
    
    path('profile/my-rentals/', views.my_rentals, name='my_rentals'),

    path('matches/create/', views.create_match, name='create_match'),
    
  
    path('notifications/', views.notifications_page, name='notifications_page'),
   
    
    path('notifications/clear/', clear_notifications, name='clear_notifications'),
    
   
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
   

    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/confirm/', views.confirm_order, name='confirm_order'),
    path('orders/', views.my_orders, name='my_orders'),
    path("product-sizes/<int:product_id>/", views.product_sizes),

    path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path("rentals/<int:rental_id>/check/", views.check_rental_availability, name="check_rental_availability"),
    path("rentals/<int:rental_id>/book/", views.book_rental, name="book_rental"),
# --- Админ-панель: заявки на организатора ---
path('admin-panel/organizer-requests/', views.admin_requests_organizer, name='admin_requests_organizer'),
path('admin-panel/organizer-requests/approve/<int:req_id>/', views.approve_organizer, name='approve_organizer'),
path('admin-panel/organizer-requests/reject/<int:req_id>/', views.reject_organizer, name='reject_organizer'),

# --- Админ-панель: заявки на аренду ---
path('admin-panel/rent-requests/', views.admin_rentals, name='admin_requests_rent'),


# --- Админ-панель: товары ---
path('admin-panel/products/', views.admin_products, name='admin_products'),
path('admin-panel/products/delete/<int:product_id>/', views.delete_product, name='delete_product'),

# --- Админ-панель: инвентарь ---
path('admin-panel/inventory/', views.admin_inventory, name='admin_inventory'),
path('admin-panel/inventory/delete/<int:item_id>/', views.delete_inventory, name='delete_inventory'),

# --- Админ-панель: организаторы ---
path('admin-panel/organizers/', views.admin_organizers, name='admin_organizers'),
path('admin-panel/organizers/remove/<int:user_id>/', views.remove_organizer, name='remove_organizer'),

# --- Админ-панель: заказы ---
path('admin-panel/orders/', views.admin_orders, name='admin_orders'),
path('admin-panel/orders/<int:order_id>/', views.admin_order_detail, name='admin_order_detail'),
path('admin-panel/orders/<int:order_id>/set-status/', views.admin_set_order_status, name='admin_set_order_status'),



# --- Админ-панель: матчи ---
path('admin-panel/matches/', views.admin_matches, name='admin_matches'),
path('admin-panel/matches/delete/<int:match_id>/', views.admin_delete_match, name='admin_delete_match'),
path('admin-panel/rent-requests/update/<int:rental_id>/', 
     views.update_rental_status, 
     name='update_rental_status'),
path("order-success/", views.order_success, name="order_success"),



]

