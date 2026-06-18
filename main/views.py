from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse


from django.db import connection



import MySQLdb
from django.conf import settings
from datetime import datetime, date, time, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Games

import json

import random

from django.db import transaction



from .forms import RegisterForm, LoginForm, OrganizerRequestForm,RentalForm
from .models import (
    Users, Profiles, Games, GameParticipants, Rental,
    OrganizerRequests, UserRentals, Products, CartItem, Notification, Orders, OrderItems,RentalSize,ProductSize,Sportshall,
)


def index(request):
    return render(request, 'main/index.html')


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('index')
    else:
        form = RegisterForm()
    return render(request, 'main/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('index')
        return render(request, 'main/login.html', {'form': form, 'error': 'Неверный логин или пароль'})
    return render(request, 'main/login.html', {'form': LoginForm()})

def games_list(request):
    auto_cancel_matches()

    now = datetime.now()

    games = Games.objects.filter(
        status='active',
        game_date__gte=now
    ).order_by('game_date', 'game_time')

    for g in games:
        # ⭐ Правильный пересчёт участников
        g.players_count = GameParticipants.objects.filter(game=g).count()

        # ⭐ Правильный расчёт свободных мест
        g.free_slots = g.max_players - g.players_count

    return render(request, 'main/games.html', {'games': games})





@login_required
def join_match(request, game_id):

    game = get_object_or_404(Games, id=game_id)

    # ❗ Матч недоступен, если организатор лишён роли
    if not game.created_by.is_organizer:
        messages.error(request, "Матч недоступен, так как организатор лишён роли.")
        return redirect('games')

    # ❗ 1. Организатор не может вступать в свой матч
    if game.created_by == request.user:
        messages.error(request, "Организатор не может вступать в свой матч.")
        return redirect('games')

    # ❗ 2. Если пользователь НЕ вошёл
    if not request.user.is_authenticated:
        messages.error(request, "Сначала войдите в аккаунт.")
        return redirect('games')

    # ❗ 3. Матч заполнен
    players_count = GameParticipants.objects.filter(game=game).count()
    if players_count >= game.max_players:
        messages.error(request, "Матч уже заполнен.")
        return redirect('games')

    # ❗ 4. Уже участвует в этом матче
    if GameParticipants.objects.filter(game=game, user=request.user).exists():
        messages.warning(request, "Вы уже присоединились к этому матчу.")
        return redirect('games')

    # ❗ 5. Проверка на другие матчи в этот же день (разница < 6 часов)
    user_matches_today = GameParticipants.objects.filter(
        user=request.user,
        game__game_date=game.game_date
    ).select_related('game')

    for gm in user_matches_today:
        diff = abs(
            datetime.combine(game.game_date, game.game_time) -
            datetime.combine(gm.game.game_date, gm.game.game_time)
        )
        if diff < timedelta(hours=6):
            messages.warning(
                request,
                "Вы не можете присоединиться — между матчами должно быть минимум 6 часов."
            )
            return redirect('games')

    # ❗ 6. Добавляем участника
    GameParticipants.objects.create(game=game, user=request.user)

    # ⭐ Уведомление участнику
    create_notification(
        request.user,
        f"Вы присоединились к матчу: {game.title}",
        link="/profile/my-matches/"
    )

    # ⭐ Уведомление организатору
    create_notification(
        game.created_by,
        f"Новый участник присоединился к вашему матчу: {game.title}",
        link="/profile/my-matches/"
    )

    # ⭐ 7. Проверка заполненности
    players_count += 1
    if players_count == game.max_players and not game.full_notification_sent:
        create_notification(
            game.created_by,
            f"Ваш матч '{game.title}' полностью заполнен!",
            link="/profile/my-matches/"
        )
        game.full_notification_sent = True
        game.save()

    # ⭐ 8. Сообщение об успехе
    messages.success(
        request,
        "Поздравляем! Вы успешно присоединились к матчу 🎉\nЖелаем отличной игры!"
    )

    return redirect('games')





def rent(request):
    rentals = Rental.objects.all()
    for rental in rentals:
        rental.has_available_sizes = rental.sizes.filter(quantity__gt=0).exists()
    return render(request, 'main/rent.html', {"rentals": rentals})



def shop(request):
    products = Products.objects.all()
    cart_count = CartItem.objects.filter(user_id=request.user.id).count() if request.user.is_authenticated else 0

    for p in products:
        # Загружаем размеры из таблицы product_sizes
        p.size_list = [s.size for s in p.sizes.all() if s.quantity > 0]

    return render(request, 'main/shop.html', {
        'products': products,
        'cart_count': cart_count
    })


def add_to_cart(request, product_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "not_authenticated"}, status=403)

    if request.method == "POST":
        product = get_object_or_404(Products, id=product_id)

        selected_size = request.POST.get("size")
        quantity = int(request.POST.get("quantity", 1))

        if not selected_size:
            return JsonResponse({"error": "no_size"}, status=400)

        cart_item = CartItem.objects.filter(
            user_id=request.user.id,
            product=product,
            selected_size=selected_size
        ).first()

        # Если товар уже есть
        if cart_item:
            # Проверяем суммарное количество
            if cart_item.quantity + quantity > 15:
                return JsonResponse({"error": "max_reached"}, status=400)

            cart_item.quantity += quantity
            cart_item.save()

            return JsonResponse({"success": True, "quantity": cart_item.quantity})

        # Если товара нет — создаём
        if quantity > 15:
            quantity = 15

        CartItem.objects.create(
            user_id=request.user.id,
            product=product,
            quantity=quantity,
            selected_size=selected_size
        )

        return JsonResponse({"success": True, "quantity": quantity})

@login_required
def cart(request):
    items = CartItem.objects.filter(user_id=request.user.id)
    cart_count = items.count()
    return render(request, 'main/cart.html', {
        'items': items,
        'cart_count': cart_count
    })



@login_required
def profile(request):
    user = Users.objects.get(id=request.user.id)
    profile = Profiles.objects.get(user=user)

    matches_count = GameParticipants.objects.filter(user=user).count()
    req = OrganizerRequests.objects.filter(user=user).order_by('-created_at').first()
    request_status = req.status if req else None
    rentals_count = UserRentals.objects.filter(user=user, status='active').count()

    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    unread_count = Notification.objects.filter(user=user, is_read=False).count()

    orders_count = Orders.objects.filter(user_id=user.id).count()

    # ⭐ ВАЖНО: правильный подсчёт корзины
    cart_items_count = CartItem.objects.filter(user_id=user.id).count()

    return render(request, 'main/profile.html', {
        'user': user,
        'profile': profile,
        'cart_items_count': cart_items_count,
        'matches_count': matches_count,
        'rentals_count': rentals_count,
        'orders_count': orders_count,
        'request_status': request_status,
        'notifications': notifications,
        'unread_count': unread_count,
    })



@login_required
def edit_profile(request):
    user = Users.objects.get(id=request.user.id)
    profile = Profiles.objects.get(user=user)

    if request.method == 'POST':
        # ЛОГИН
        user.username = request.POST.get('username')

        # ИМЯ
        user.first_name = request.POST.get('name')

        # EMAIL
        user.email = request.POST.get('email')

        # ТЕЛЕФОН
        profile.phone = request.POST.get('phone')

        # АВАТАР
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']

        user.save()
        profile.save()
        return redirect('profile')

    return render(request, 'main/edit_profile.html', {'user': user, 'profile': profile})





def update_avatar(request):
    profile = Profiles.objects.get(user=request.user)
    if request.method == 'POST' and request.FILES.get('avatar'):
        profile.avatar = request.FILES['avatar']
        profile.save()
    return redirect('profile')


def user_logout(request):
    logout(request)
    return redirect('index')

def my_matches(request):
    user = request.user

    user_games_ids = GameParticipants.objects.filter(user=user).values_list('game_id', flat=True)

    games = Games.objects.filter(
        id__in=user_games_ids,
        status='active'
    )

    organizer_games = Games.objects.filter(
        created_by=user,
        status='active'
    )

    games = (games | organizer_games).distinct()

    return render(request, 'main/my_matches.html', {'games': games})



def leave_match(request, game_id):
    game = get_object_or_404(Games, id=game_id)
    participation = GameParticipants.objects.filter(game=game, user=request.user)

    if participation.exists():
        participation.delete()

        # ⭐ Уведомление участнику
        create_notification(
            request.user,
            f"Вы покинули матч: {game.title}",
            link="/profile/my-matches/"
        )

        # ⭐ Уведомление организатору (если это не он сам)
        if game.created_by != request.user:
            create_notification(
                game.created_by,
                f"Участник покинул ваш матч: {game.title}",
                link="/profile/my-matches/"
            )

        messages.success(request, "Вы покинули матч")
    else:
        messages.warning(request, "Вы не участвуете в этом матче")

    return redirect('my_matches')




@login_required
def delete_match(request, game_id):
    game = get_object_or_404(Games, id=game_id)

    # Проверка прав
    if not (request.user.is_admin or request.user == game.created_by):
        return redirect("profile")

    # Все участники матча
    participants = GameParticipants.objects.filter(game_id=game.id)

    # Уведомляем участников
    for gp in participants:
        create_notification(
            gp.user,
            f"Матч «{game.title}» был удалён организатором.",
            link="/games/"
        )

    # Удаляем участников
    participants.delete()

    # Уведомляем организатора (если удаляет админ)
    if request.user != game.created_by:
        create_notification(
            game.created_by,
            f"Ваш матч «{game.title}» был удалён администратором.",
            link="/games/"
        )

    # Удаляем сам матч
    game.delete()

    messages.success(request, "Матч успешно удалён.")
    return redirect("my_matches")





@login_required
def become_organizer(request):
    existing = OrganizerRequests.objects.filter(user=request.user).order_by('-created_at').first()

    # Если уже отправил и она на рассмотрении
    if existing and existing.status == 'pending':
        messages.warning(request, "Вы уже отправили заявку. Ожидайте ответа администратора.")
        return redirect('profile')

    if request.method == 'POST':
        form = OrganizerRequestForm(request.POST)
    if form.is_valid():
        req = form.save(commit=False)
        req.user = request.user
        req.phone = request.POST.get('phone')
        req.save()

        # ⭐ Уведомление админу
        admins = Users.objects.filter(is_admin=True)
        for admin in admins:
            create_notification(
                admin,
                f"Новая заявка на организатора от {request.user.username}.",
                link="/admin-panel/organizer-requests/"
            )

        # ⭐ Если в профиле нет телефона — записываем
        profile = Profiles.objects.get(user=request.user)
        if not profile.phone:
            profile.phone = req.phone
            profile.save()

        messages.success(request, "Заявка отправлена!")
        return redirect('profile')

    else:
        form = OrganizerRequestForm()

    return render(request, 'main/become_organizer.html', {'form': form})


def check_availability(request, item_id):
    if request.method == "POST":
        start_date = request.POST.get("start_date")
        start_time = request.POST.get("start_time")
        end_date = request.POST.get("end_date")
        end_time = request.POST.get("end_time")

        start_dt = datetime.fromisoformat(f"{start_date} {start_time}")
        end_dt = datetime.fromisoformat(f"{end_date} {end_time}")

        item = Rental.objects.get(id=item_id)

        overlapping = UserRentals.objects.filter(
            item=item,
            status="active",
            start_datetime__lte=end_dt,
            end_datetime__gte=start_dt
        ).count()

        available = item.quantity - overlapping

        if available > 0:
            return JsonResponse({"available": True, "message": f"Доступно: {available} шт."})
        else:
            return JsonResponse({"available": False, "message": "Нет свободных предметов."})


@login_required
def book_item(request, item_id):

    if request.method == "POST":
        start_date = request.POST.get("start_date")
        start_time = request.POST.get("start_time")
        end_date = request.POST.get("end_date")
        end_time = request.POST.get("end_time")

        start_dt = datetime.fromisoformat(f"{start_date} {start_time}")
        end_dt = datetime.fromisoformat(f"{end_date} {end_time}")

        item = Rental.objects.get(id=item_id)

        UserRentals.objects.create(
            user=request.user,
            item=item,
            start_datetime=start_dt,
            end_datetime=end_dt,
            status="active"
        )

        # уведомление
        create_notification(
            request.user,
            f"Вы забронировали: {item.name}",
            link="/profile/my-rentals/"
        )

        # остаёмся на той же странице
        return redirect(request.META.get("HTTP_REFERER", "rent"))


def my_rentals(request):
    user = request.user

    rentals = UserRentals.objects.filter(user=user).select_related('item').order_by('-created_at')

    # ⭐ Добавляем вычисляемую стоимость
    for r in rentals:
        delta = r.end_datetime - r.start_datetime
        days = delta.days
        if delta.seconds > 0:
            days += 1
        r.total_price = days * r.item.price

    return render(request, 'main/my_rentals.html', {
        'rentals': rentals
    })



def get_halls():
    """Получаем список спортзалов из MySQL вручную"""
    db = MySQLdb.connect(
        host=settings.DATABASES['default']['HOST'],
        user=settings.DATABASES['default']['USER'],
        passwd=settings.DATABASES['default']['PASSWORD'],
        db=settings.DATABASES['default']['NAME'],
        charset='utf8'
    )
    cursor = db.cursor()
    cursor.execute("SELECT id, name FROM sportshall")
    halls = cursor.fetchall()
    db.close()
    return halls


def get_hall_name(hall_id):
    """Получаем название спортзала по ID"""
    db = MySQLdb.connect(
        host=settings.DATABASES['default']['HOST'],
        user=settings.DATABASES['default']['USER'],
        passwd=settings.DATABASES['default']['PASSWORD'],
        db=settings.DATABASES['default']['NAME'],
        charset='utf8'
    )
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sportshall WHERE id = %s", [hall_id])
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None

@login_required
def create_match(request):

    if not request.user.is_organizer:
        return redirect('games')

    halls = Sportshall.objects.all()

    if request.method == 'GET':
        storage = messages.get_messages(request)
        for _ in storage:
            pass

    if request.method == 'POST':

        form_data = request.POST
        errors = {}

        title = form_data.get('title', '').strip()
        hall_id = form_data.get('location')
        game_date_str = form_data.get('game_date')
        game_time_str = form_data.get('game_time')
        fmt = form_data.get('format')
        level = form_data.get('level')
        max_players_str = form_data.get('max_players')
        price_str = form_data.get('price')
        image = request.FILES.get('image')

        # --- Проверка картинки ---
        if not image:
            errors["error_image"] = "Пожалуйста, загрузите изображение."

        # --- Проверка зала ---
        try:
            hall = Sportshall.objects.get(id=hall_id)
        except:
            errors["error_location"] = "Выберите корректный спортзал."

        # --- Парсим дату и время ---
        try:
            game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
            game_time = datetime.strptime(game_time_str, "%H:%M").time()
        except:
            errors["error_time"] = "Некорректная дата или время."

        # --- Проверка на прошлое ---
        now = datetime.now()
        if game_date < now.date() or (game_date == now.date() and game_time <= now.time()):
            errors["error_time"] = "Нельзя создать матч в прошлом."

        # --- Проверка минимума/максимума игроков ---
        limits = {
            "2x2": {"min": 4, "max": 4},
            "3x3": {"min": 6, "max": 6},
            "6x6": {"min": 12, "max": 12},
        }

        try:
            max_players = int(max_players_str)
        except:
            max_players = 0

        if fmt in limits:
            min_p = limits[fmt]["min"]
            max_p = limits[fmt]["max"]
            if not (min_p <= max_players <= max_p):
                errors["error_max"] = f"Для формата {fmt} игроков должно быть от {min_p} до {max_p}."

        # --- Проверка цены ---
        try:
            price = int(price_str)
            if price < 0:
                raise ValueError
        except:
            errors["error_price"] = "Введите корректную цену."

        # --- Если есть ошибки ---
        if errors:
            return render(request, 'main/create_match.html', {
                "halls": halls,
                "form_data": form_data,
                **errors
            })

        # --- Проверка ±4 часа ---
        dt = datetime.combine(game_date, game_time)
        existing_games = Games.objects.filter(sportshall=hall, game_date=game_date)

        for g in existing_games:
            existing_dt = datetime.combine(g.game_date, g.game_time)
            if abs(dt - existing_dt) < timedelta(hours=4):
                return render(request, 'main/create_match.html', {
                    "halls": halls,
                    "form_data": form_data,
                    "error_time": "В этом спортзале уже есть матч в пределах 4 часов."
                })

        # --- Создание матча ---
        Games.objects.create(
            title=title,
            game_date=game_date,
            game_time=game_time,
            location=hall.name,   # ← строка (название)
            sportshall=hall,      # ← ForeignKey (для адреса)
            image=image,
            format=fmt,
            level=level,
            created_by=request.user,
            status='active',
            max_players=max_players,
            players_count=0,
            price=price
        )

        messages.success(request, "Матч успешно создан!")
        return redirect('games')

    return render(request, 'main/create_match.html', {"halls": halls})

def auto_cancel_matches():
    # Текущее время (naive, в МСК, т.к. USE_TZ = False и TIME_ZONE = "Europe/Moscow")
    now = datetime.now()

    # Берём все активные матчи
    games = Games.objects.filter(status='active')

    for game in games:
        # Собираем дату и время матча в один datetime (naive)
        game_datetime = datetime.combine(game.game_date, game.game_time)

        participants = game.gameparticipants_set.count()

        # 1) Матч уже прошёл → завершить
        if game_datetime <= now:
            game.status = 'finished'
            game.save()

            # Уведомления участникам
            for p in game.gameparticipants_set.all():
                create_notification(
                    p.user,
                    f"Матч '{game.title}' завершён.",
                    link="/profile/my-matches/"
                )

            # Уведомление организатору
            create_notification(
                game.created_by,
                f"Ваш матч '{game.title}' завершён.",
                link="/profile/my-matches/"
            )

            continue

        # 2) До матча < 2 часов и участников мало → авто‑отмена
        if (game_datetime - now < timedelta(hours=2)) and (participants < game.min_players):
            game.status = 'cancelled'
            game.save()

            # Уведомления участникам
            for p in game.gameparticipants_set.all():
                create_notification(
                    p.user,
                    f"Матч '{game.title}' был автоматически отменён из‑за нехватки участников.",
                    link="/games/"
                )

            # Уведомление организатору
            create_notification(
                game.created_by,
                f"Ваш матч '{game.title}' был автоматически отменён системой.",
                link="/games/"
            )

            continue

        # 3) Напоминание за 2 часа до матча
        if not game.notification_sent and (game_datetime - now < timedelta(hours=2)):
            # Уведомления участникам
            for p in game.gameparticipants_set.all():
                create_notification(
                    p.user,
                    f"Матч '{game.title}' начнётся через 2 часа!",
                    link="/profile/my-matches/"
                )

            # Уведомление организатору
            create_notification(
                game.created_by,
                f"Ваш матч '{game.title}' начнётся через 2 часа!",
                link="/profile/my-matches/"
            )

            game.notification_sent = True
            game.save()




def notifications_page(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    all_read = not Notification.objects.filter(user=request.user, is_read=False).exists()

    return render(request, 'main/notifications.html', {
        'notifications': notifications,
        'unread_count': 0,  # лампочка гаснет
    })





def create_notification(user, text, link=None):
    Notification.objects.create(
        user=user,
        text=text,
        link=link,
        is_read=False,
        created_at=timezone.now()
    )

def auto_rental_notifications():
    now = datetime.now()

    rentals = UserRentals.objects.filter(status='active')

    for r in rentals:
        end_dt = r.end_datetime

        # 1) Напоминание за 2 часа до конца аренды
        if not r.reminder_sent and (end_dt - now < timedelta(hours=2)) and end_dt > now:
            create_notification(
                r.user,
                f"Ваша аренда '{r.item.name}' заканчивается через 2 часа.",
                link="/profile/my-rentals/"
            )

            r.reminder_sent = True
            r.save()

        if not r.overdue_sent and end_dt <= now:
            create_notification(
        r.user,
        f"Срок аренды '{r.item.name}' истёк. Пожалуйста, верните предмет.",
        link="/profile/my-rentals/"
    )

    r.overdue_sent = True
    r.save()

    # ⭐ Уведомление админу
    admins = Users.objects.filter(is_admin=True)
    for admin in admins:
        create_notification(
            admin,
            f"Пользователь {r.user.username} просрочил аренду '{r.item.name}'.",
            link="/admin-panel/rentals/"
        )



def mark_all_notifications_read(request):
    if request.user.is_authenticated:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"status": "ok"})


def clear_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    return redirect('notifications_page')

@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user).update(is_read=True)
    return redirect('notifications_page')



@login_required
def remove_from_cart(request, item_id):
    if request.method == "POST":
        try:
            item = CartItem.objects.get(id=item_id, user_id=request.user.id)

            item.delete()
            return JsonResponse({"success": True})
        except CartItem.DoesNotExist:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


@login_required
def update_cart(request, item_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            quantity = int(data.get("quantity", 1))

            # Ограничения
            if quantity < 1:
                quantity = 1
            if quantity > 30:
                quantity = 30

            # ВАЖНО: user_id вместо user
            item = CartItem.objects.get(id=item_id, user_id=request.user.id)
            item.quantity = quantity
            item.save()

            return JsonResponse({"success": True, "quantity": item.quantity})

        except CartItem.DoesNotExist:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)
def admin_requests_organizer(request):
    if not request.user.is_admin:
        return redirect('profile')

    requests_list = OrganizerRequests.objects.filter(status='pending')



    return render(request, 'admin/requests_organizer.html', {'requests': requests_list})

def admin_products(request):

    if not request.user.is_admin:
        return redirect('profile')

    products = Products.objects.all()  
    return render(request, 'admin/products.html', {'products': products})
def admin_inventory(request):
    if not request.user.is_admin:
        return redirect('profile')

    inventory = Rental.objects.all()  
    return render(request, 'admin/inventory.html', {'inventory': inventory})
def admin_organizers(request):
    if not request.user.is_admin:
        return redirect('profile')

    organizers = Users.objects.filter(is_organizer=True)
    return render(request, 'admin/organizers.html', {'organizers': organizers})




from django.db import connection
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def remove_organizer(request, user_id):
    print("🔥 REMOVE ORGANIZER STARTED")

    user = get_object_or_404(Users, id=user_id)

    # Все матчи, созданные этим пользователем
    games = Games.objects.filter(created_by=user)

    for game in games:

        # Участники матча
        participants = GameParticipants.objects.filter(game_id=game.id)

        # Уведомляем участников
        for gp in participants:
            create_notification(
                gp.user,
                f"Матч «{game.title}» был удалён, так как организатор лишён роли.",
                link="/games/"
            )

        # Удаляем участников
        participants.delete()

        # Удаляем сам матч
        game.delete()

    # Снимаем роль организатора
    user.is_organizer = False
    user.save()

    # Уведомляем самого организатора
    create_notification(
        user,
        "Ваша роль организатора была снята. Все ваши матчи были удалены.",
        link="/games/"
    )

    # ❗ УБРАНО messages.success — чтобы сообщение НЕ улетало на другие страницы
    return redirect("admin_organizers")








def approve_organizer(request, req_id):
    if not request.user.is_admin:
        return redirect('profile')

    req = OrganizerRequests.objects.get(id=req_id)
    req.status = 'approved'
    req.save()

    user = req.user
    user.is_organizer = True
    user.save()

    return render(request, 'admin/action_result.html', {
        'title': 'Заявка одобрена',
        'message': f'Пользователь {user.username} теперь организатор.',
        'back_url': reverse('admin_requests_organizer')
    })
def reject_organizer(request, req_id):
    if not request.user.is_admin:
        return redirect('profile')

    req = OrganizerRequests.objects.get(id=req_id)
    req.status = 'rejected'
    req.save()

    return render(request, 'admin/action_result.html', {
        'title': 'Заявка отклонена',
        'message': f'Вы отклонили заявку пользователя {req.user.username}.',
        'back_url': reverse('admin_requests_organizer')
    })


def delete_product(request, product_id):
    if not request.user.is_admin:
        return redirect('profile')

    product = Products.objects.get(id=product_id)
    product.delete()

    return render(request, 'admin/action_result.html', {
        'title': 'Товар удалён',
        'message': f'Товар "{product.name}" был успешно удалён.',
        'back_url': reverse('admin_products')
    })
def delete_inventory(request, item_id):
    if not request.user.is_admin:
        return redirect('profile')

    item = Rental.objects.get(id=item_id)
    item.delete()

    return render(request, 'admin/action_result.html', {
        'title': 'Инвентарь удалён',
        'message': f'Инвентарь "{item.name}" был успешно удалён.',
        'back_url': reverse('admin_inventory')
    })


@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user_id=request.user.id)
    total = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, "main/checkout.html", {
        "cart_items": cart_items,
        "total": total
    })
@login_required
def confirm_order(request):
    if request.method != "POST":
        return redirect("checkout")

    user = request.user

    cart_items = CartItem.objects.filter(user_id=user.id)
    if not cart_items.exists():
        return redirect("checkout")

    total_price = sum(item.product.price * item.quantity for item in cart_items)

    # ВАЖНО: user=user, а не user_id=user.id
    order = Orders.objects.create(
        user=user,
        pvz=request.POST.get("pvz"),
        pickup_time=request.POST.get("pickup_time"),
        comment=request.POST.get("comment", ""),
        total_price=total_price,
        status="new"
    )
    admins = Users.objects.filter(is_admin=True)
    for admin in admins:
        create_notification(
            admin,
            f"Новый заказ #{order.id} от {order.user.username}.",
            link=f"/admin-panel/orders/{order.id}/"
    )
    for item in cart_items:
        OrderItems.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            size=item.selected_size,
            price=item.product.price
        )

    cart_items.delete()

    return redirect("order_success")


@login_required

def my_orders(request):
    orders = Orders.objects.filter(user_id=request.user.id).order_by('-created_at')
    return render(request, "main/my_orders.html", {"orders": orders})


def order_success(request):
    return render(request, "main/order_success.html")


@login_required
def admin_orders(request):
    if not request.user.is_admin:
        return redirect('profile')

    orders = Orders.objects.all().order_by('-created_at')

    return render(request, 'admin/orders.html', {
        'orders': orders
    })


@login_required
def admin_order_detail(request, order_id):
    if not request.user.is_admin:
        return redirect('profile')

    order = get_object_or_404(Orders, id=order_id)
    items = OrderItems.objects.filter(order=order)

    return render(request, 'admin/order_detail.html', {
        'order': order,
        'items': items
    })


@login_required
def admin_set_order_status(request, order_id):
    if not request.user.is_admin:
        return redirect('profile')

    order = get_object_or_404(Orders, id=order_id)
    new_status = request.POST.get('status')

    # допустимые статусы
    allowed_statuses = ['new', 'processing', 'ready', 'completed']

    if new_status in allowed_statuses:
        order.status = new_status
        order.save()

        # уведомление пользователю
        text = None
        if new_status == 'processing':
            text = f"Ваш заказ №{order.id} готовится."
        elif new_status == 'ready':
            text = f"Ваш заказ №{order.id} готов к выдаче."
        elif new_status == 'completed':
            text = f"Ваш заказ №{order.id} завершён."

        if text:
            create_notification(order.user, text, "/orders/")

    return redirect('admin_order_detail', order_id=order.id)
@login_required
def approve_organizer(request, req_id):
    if not request.user.is_admin:
        return redirect("profile")

    req = get_object_or_404(OrganizerRequests, id=req_id)

    # Делаем пользователя организатором
    req.user.is_organizer = True
    req.user.save()

    # Обновляем статус заявки
    req.status = "approved"
    req.save()

    # Уведомление пользователю
    Notification.objects.create(
        user=req.user,
        type="organizer_request",
        text="Ваша заявка на организатора одобрена!",
        link="/profile/",
        is_read=False,
        created_at=timezone.now()
    )

    return redirect("admin_requests_organizer")
@login_required
def reject_organizer(request, req_id):
    if not request.user.is_admin:
        return redirect("profile")

    req = get_object_or_404(OrganizerRequests, id=req_id)

    # Обновляем статус заявки
    req.status = "rejected"
    req.save()

    # Уведомление пользователю
    Notification.objects.create(
        user=req.user,
        type="organizer_request",
        text="Ваша заявка на организатора отклонена.",
        link="/profile/",
        is_read=False,
        created_at=timezone.now()
    )

    return redirect("admin_requests_organizer")

@login_required
def delete_inventory(request, item_id):
    if not request.user.is_admin:
        return redirect('profile')

    item = get_object_or_404(Rental, id=item_id)
    item.delete()

    return redirect('admin_inventory')
@login_required
def admin_rentals(request):
    if not request.user.is_admin:
        return redirect('profile')

    status_filter = request.GET.get("status")

    rentals = UserRentals.objects.select_related("user", "item").order_by("-created_at")

    if status_filter:
        rentals = rentals.filter(status=status_filter)

    return render(request, "admin/rentals.html", {
        "rentals": rentals,
        "status_filter": status_filter,
    })

def rent_item(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)

    if request.method == "POST":
        form = RentalForm(request.POST, rental=rental)

        if form.is_valid():
            size_obj = form.cleaned_data.get("size")

            # Если есть размеры
            if rental.sizes.exists():
                if not size_obj or size_obj.quantity <= 0:
                    form.add_error("size", "Этот размер недоступен.")
                else:
                    size_obj.quantity -= 1
                    size_obj.save()

                    rental_record = form.save(commit=False)
                    rental_record.user = request.user
                    rental_record.item = rental
                    rental_record.save()

                    # уведомление
                    create_notification(
                        request.user,
                        f"Вы забронировали: {rental.name}",
                        link="/profile/my-rentals/"
                    )

                    return redirect(request.META.get("HTTP_REFERER", "rent"))

            else:
                # Если размеров нет
                if rental.quantity <= 0:
                    form.add_error(None, "Нет в наличии.")
                else:
                    rental.quantity -= 1
                    rental.save()

                    rental_record = form.save(commit=False)
                    rental_record.user = request.user
                    rental_record.item = rental
                    rental_record.save()

                    # уведомление
                    create_notification(
                        request.user,
                        f"Вы забронировали: {rental.name}",
                        link="/profile/my-rentals/"
                    )

                    return redirect(request.META.get("HTTP_REFERER", "rent"))

    else:
        form = RentalForm(rental=rental)

    return render(request, "main/rental_detail.html", {
        "rental": rental,
        "form": form
    })

def check_rental_availability(request, rental_id):
    
    rental = get_object_or_404(Rental, id=rental_id)

    start_date = request.POST.get("start_date")
    start_time = request.POST.get("start_time")
    end_date = request.POST.get("end_date")
    end_time = request.POST.get("end_time")
    size_id = request.POST.get("size_id")

    start = datetime.fromisoformat(f"{start_date} {start_time}")
    end = datetime.fromisoformat(f"{end_date} {end_time}")

    # --- ЕСЛИ ВЫБРАН РАЗМЕР ---
    if size_id:
        size = get_object_or_404(RentalSize, id=size_id)

        # брони по конкретному размеру
        booked = UserRentals.objects.filter(
            size=size,
            start_datetime__lt=end,
            end_datetime__gt=start,
            status="active"
        ).count()

        # доступно только по этому размеру
        available = max(size.quantity - booked, 0)

    # --- ЕСЛИ РАЗМЕРОВ НЕТ ---
    else:
        booked = UserRentals.objects.filter(
            item=rental,
            start_datetime__lt=end,
            end_datetime__gt=start,
            status="active"
        ).count()

        available = max(rental.quantity - booked, 0)

    return JsonResponse({
        "available": available > 0,
        "message": f"Доступно: {available} шт." if available > 0 else "❌ Нет свободных предметов"
    })


def book_rental(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)

    if request.method != "POST":
        return redirect("rent")

    start_date = request.POST.get("start_date")
    start_time = request.POST.get("start_time")
    end_date = request.POST.get("end_date")
    end_time = request.POST.get("end_time")
    size_id = request.POST.get("size_id")

    start = datetime.fromisoformat(f"{start_date} {start_time}")
    end = datetime.fromisoformat(f"{end_date} {end_time}")

    # --- ЕСЛИ ВЫБРАН РАЗМЕР ---
    if size_id:
        size = get_object_or_404(RentalSize, id=size_id)

        # проверяем остаток
        if size.quantity <= 0:
            messages.error(request, "Этот размер закончился")
            return redirect("rent")

        # уменьшаем количество ТОЛЬКО размера
        size.quantity -= 1
        size.save()

        # создаём бронь
        UserRentals.objects.create(
            user=request.user,
            item=rental,
            size=size,
            start_datetime=start,
            end_datetime=end,
            status="active"
        )

    # --- ЕСЛИ РАЗМЕРОВ НЕТ ---
    else:
        if rental.quantity <= 0:
            messages.error(request, "Нет в наличии")
            return redirect("rent")

        # уменьшаем общее количество
        rental.quantity -= 1
        rental.save()

        # создаём бронь
        UserRentals.objects.create(
            user=request.user,
            item=rental,
            start_datetime=start,
            end_datetime=end,
            status="active"
        )

    messages.success(request, "Аренда успешно оформлена!")
    return redirect("profile")

def product_sizes(request, product_id):
    sizes = ProductSize.objects.filter(product_id=product_id, quantity__gt=0)
    return JsonResponse({"sizes": [s.size for s in sizes]})
@login_required
def admin_matches(request):
    if not request.user.is_admin:
        return redirect('index')

    matches = Games.objects.order_by('-game_date', '-game_time', '-id')

    return render(request, 'admin/admin_matches.html', {
        'matches': matches
    })

@login_required
def admin_delete_match(request, match_id):
    game = get_object_or_404(Games, id=match_id)

    participants = GameParticipants.objects.filter(game_id=game.id)
    for gp in participants:
        create_notification(
            gp.user,
            f"Матч «{game.title}» был удалён администратором.",
            link="/games/"
        )

    if game.created_by:
        create_notification(
            game.created_by,
            f"Ваш матч «{game.title}» был удалён администратором.",
            link="/games/"
        )

    GameParticipants.objects.filter(game_id=game.id).delete()
    game.delete()

    return redirect("admin_matches")

@login_required
def update_rental_status(request, rental_id):
    rental = UserRentals.objects.get(id=rental_id)
    new_status = request.POST.get("status")

    # Обновляем ENUM через update()
    UserRentals.objects.filter(id=rental_id).update(status=new_status)

    # Кнопка перехода
    link = '<a href="/profile/my-rentals/">Перейти</a>'


    # Уведомления
    if new_status == "booked":
        create_notification(rental.user, f"Ваша аренда подтверждена! Предмет забронирован. {link}")
    elif new_status == "active":
        create_notification(rental.user, f"Вы получили предмет. Аренда началась. {link}")
    elif new_status == "awaiting_return":
        create_notification(rental.user, f"Пожалуйста, верните предмет. Срок аренды подходит к концу. {link}")
    elif new_status == "completed":
        create_notification(rental.user, f"Аренда завершена. Спасибо за использование сервиса! {link}")
    elif new_status == "cancelled":
        create_notification(rental.user, f"Ваша аренда отменена. {link}")

    messages.success(request, "Статус аренды обновлён.")
    return redirect('admin_requests_rent')

