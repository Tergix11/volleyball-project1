from django.contrib import admin
from django.utils.html import format_html
from .models import (
    OrganizerRequests, Users, Profiles, Games, GameParticipants,
    Rental, UserRentals, Notification, Products
)
from .views import create_notification


# ---------------------------------------
# ЗАЯВКИ НА ОРГАНИЗАТОРА
# ---------------------------------------

@admin.action(description="Одобрить выбранные заявки")
def approve_requests(modeladmin, request, queryset):
    for req in queryset:
        user = req.user
        user.is_organizer = True
        user.save()
        req.status = "approved"
        req.save()
        create_notification(
            user,
            "Ваша заявка на получение статуса организатора одобрена!",
            link="/profile/"
        )


@admin.action(description="Отклонить выбранные заявки")
def reject_requests(modeladmin, request, queryset):
    for req in queryset:
        user = req.user
        user.is_organizer = False
        user.save()
        req.status = "rejected"
        req.save()
        create_notification(
            user,
            "Ваша заявка на получение статуса организатора отклонена.",
            link="/profile/"
        )


@admin.register(OrganizerRequests)
class OrganizerRequestsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username",)
    actions = [approve_requests, reject_requests]

    def delete_model(self, request, obj):
        user = obj.user
        user.is_organizer = False
        user.save()
        create_notification(
            user,
            "Ваша заявка на получение статуса организатора была удалена администратором.",
            link="/profile/"
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            user = obj.user
            user.is_organizer = False
            user.save()
            create_notification(
                user,
                "Ваша заявка на получение статуса организатора была удалена администратором.",
                link="/profile/"
            )
        super().delete_queryset(request, queryset)


# ---------------------------------------
# ПОЛЬЗОВАТЕЛИ
# ---------------------------------------

@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_organizer")
    search_fields = ("username", "email")
    list_filter = ("is_organizer",)


# ---------------------------------------
# ПРОФИЛИ
# ---------------------------------------

@admin.register(Profiles)
class ProfilesAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__username", "phone")


# ---------------------------------------
# МАТЧИ
# ---------------------------------------

@admin.register(Games)
class GamesAdmin(admin.ModelAdmin):
    list_display = ("title", "game_date", "game_time", "location", "status")
    list_filter = ("status", "game_date")
    search_fields = ("title", "location")


# ---------------------------------------
# УЧАСТНИКИ МАТЧЕЙ
# ---------------------------------------

@admin.register(GameParticipants)
class GameParticipantsAdmin(admin.ModelAdmin):
    list_display = ("game", "user")
    search_fields = ("game__title", "user__username")


# ---------------------------------------
# АРЕНДА ИНВЕНТАРЯ
# ---------------------------------------

@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity")
    search_fields = ("name",)


# ---------------------------------------
# АРЕНДЫ ПОЛЬЗОВАТЕЛЕЙ
# ---------------------------------------

@admin.register(UserRentals)
class UserRentalsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "item",
        "start_datetime",
        "end_datetime",
        "colored_status",
    )

    list_filter = ("status", "start_datetime", "end_datetime")
    search_fields = ("user__username", "item__name")

    actions = ["approve_return", "reject_return"]

    @admin.display(description="Статус")
    def colored_status(self, obj):
        colors = {
            "active": "green",
            "return_requested": "orange",
            "returned": "gray",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    # -----------------------------
    # Принять возврат
    # -----------------------------
    @admin.action(description="Принять возврат")
    def approve_return(self, request, queryset):
        for rental in queryset:
            rental.status = "returned"
            rental.save()

            # уведомление пользователю
            create_notification(
                rental.user,
                f"Ваш возврат инвентаря «{rental.item.name}» принят администратором.",
                link="/profile/my-rentals/"
            )

    # -----------------------------
    # Отклонить возврат
    # -----------------------------
    @admin.action(description="Отклонить возврат")
    def reject_return(self, request, queryset):
        for rental in queryset:
            rental.status = "active"
            rental.save()

            # уведомление пользователю
            create_notification(
                rental.user,
                f"Ваш запрос на возврат инвентаря «{rental.item.name}» отклонён администратором.",
                link="/profile/my-rentals/"
            )



# ---------------------------------------
# УВЕДОМЛЕНИЯ
# ---------------------------------------

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "text", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "text")


# ---------------------------------------
# ТОВАРЫ
# ---------------------------------------

@admin.register(Products)
class ProductsAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "brand", "size", "price", "created_at")
    search_fields = ("name", "brand")
    list_filter = ("brand", "size")
