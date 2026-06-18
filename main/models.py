from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


# -----------------------------
# Пользователь
# -----------------------------
class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, is_organizer=False):
        if not username:
            raise ValueError("Имя пользователя обязательно")

        user = self.model(
            username=username,
            email=self.normalize_email(email),
            is_organizer=is_organizer
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None):
        user = self.create_user(username, email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class Users(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    username = models.CharField("Имя пользователя", max_length=50, unique=True)
    first_name = models.CharField("Имя", max_length=100, null=True, blank=True)
    email = models.EmailField("Email", max_length=100, unique=True, null=True)
    is_organizer = models.BooleanField("Организатор", default=False)
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)
    is_admin = models.BooleanField("Администратор", default=False)
    is_staff = models.BooleanField("Сотрудник", default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        managed = False



# -----------------------------
# Профиль
# -----------------------------
class Profiles(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")

    rating = models.FloatField("Рейтинг", default=0)
    games_created = models.IntegerField("Создано игр", default=0)
    games_completed = models.IntegerField("Завершено игр", default=0)
    is_trusted = models.BooleanField("Доверенный", default=False)

    phone = models.CharField("Телефон", max_length=20, null=True, blank=True)

    avatar = models.ImageField(
        "Аватар",
        upload_to='avatars/',
        null=True,
        blank=True,
        default='avatars/default.png'
    )

    class Meta:
        db_table = 'profiles'
        managed = False
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f"Профиль {self.user.username}"


# -----------------------------
# Заявки на организатора
# -----------------------------
class OrganizerRequests(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")

    name = models.CharField("Имя", max_length=100)
    phone = models.CharField("Телефон", max_length=20)
    email = models.EmailField("Email")
    message = models.TextField("Сообщение", default="Хочу стать организатором")

    status = models.CharField(
        "Статус",
        max_length=10,
        choices=[
            ('pending', 'В ожидании'),
            ('approved', 'Одобрено'),
            ('rejected', 'Отклонено')
        ],
        default='pending'
    )

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        db_table = 'organizer_requests'
        verbose_name = "Заявка на организатора"
        verbose_name_plural = "Заявки на организатора"


    def __str__(self):
        return f"{self.user.username} — {self.status}"


class Sportshall(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    price = models.IntegerField(default=0)

    class Meta:
        db_table = 'sportshall'  # Используем существующую таблицу

    def __str__(self):
        return self.name
class Games(models.Model):
    id = models.IntegerField(primary_key=True)

    title = models.CharField("Название", max_length=255)

    game_date = models.DateField("Дата игры")
    game_time = models.TimeField("Время игры")

    # Старое поле location оставляем, чтобы не ломать существующие данные
    location = models.CharField("Локация", max_length=255)

    image = models.ImageField("Изображение", upload_to='games/', blank=True, null=True)
    format = models.CharField("Формат", max_length=50, blank=True, null=True)
    level = models.CharField("Уровень", max_length=50, blank=True, null=True)

    status = models.CharField("Статус", max_length=50, default='active')

    max_players = models.IntegerField("Максимум игроков", default=12)
    players_count = models.IntegerField("Текущее количество игроков", default=0)

    # Новая связь с таблицей sportshall
    sportshall = models.ForeignKey(
        Sportshall,
        on_delete=models.DO_NOTHING,
        db_column='sportshall_id',   # Используем существующее поле в БД
        null=True
    )

    price = models.IntegerField(default=0)

    created_by = models.ForeignKey(Users, on_delete=models.CASCADE, verbose_name="Создатель")
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    notification_sent = models.BooleanField("Уведомление отправлено", default=False)

    @property
    def min_players(self):
        if self.format == "2x2":
            return 4
        if self.format == "3x3":
            return 6
        if self.format == "6x6":
            return 12
        return 2

    class Meta:
        db_table = 'games'
        managed = True
        verbose_name = "Игра"
        verbose_name_plural = "Игры"

    def __str__(self):
        return self.title


# -----------------------------
# Участники игр
# -----------------------------
class GameParticipants(models.Model):
    id = models.AutoField(primary_key=True)
    game = models.ForeignKey(Games, on_delete=models.CASCADE, db_column='game_id', verbose_name="Игра")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")
    joined_at = models.DateTimeField("Дата вступления", auto_now_add=True)

    class Meta:
        db_table = 'game_participants'
        managed = True
        verbose_name = "Участник игры"
        verbose_name_plural = "Участники игр"


# -----------------------------
# Подтверждения участия
# -----------------------------
class GameConfirmations(models.Model):
    id = models.AutoField(primary_key=True)
    game = models.ForeignKey(Games, on_delete=models.CASCADE, db_column='game_id', verbose_name="Игра")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")
    confirmed_at = models.DateTimeField("Дата подтверждения", auto_now_add=True)

    class Meta:
        db_table = 'game_confirmations'
        managed = False
        verbose_name = "Подтверждение участия"
        verbose_name_plural = "Подтверждения участия"


# -----------------------------
# Товары
# -----------------------------
class Products(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField("Название", max_length=100)
    brand = models.CharField("Бренд", max_length=50, null=True)
    size = models.CharField("Размер", max_length=20, null=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    description = models.TextField("Описание", null=True)
    image = models.CharField("Картинка", max_length=255, null=True, db_column='image')
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        db_table = 'products'   # ← ВАЖНО!
        managed = False
        verbose_name = "Товар"
        verbose_name_plural = "Товары"




# -----------------------------
# Аренда инвентаря
# -----------------------------
class Rental(models.Model):
    id = models.AutoField(primary_key=True)

    name = models.CharField("Название", max_length=255)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    description = models.TextField("Описание", blank=True, null=True)
    is_available = models.BooleanField("Доступно", default=True)
    image = models.ImageField("Изображение", upload_to='rentals/', blank=True, null=True)

    quantity = models.IntegerField("Количество", default=1)

    class Meta:
        db_table = 'rentals'
        managed = False
        verbose_name = "Аренды инвентаря"
        verbose_name_plural = "Аренды инвентаря"

    def __str__(self):
        return self.name


# -----------------------------
# Аренды пользователей
# -----------------------------
class UserRentals(models.Model):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")
    item = models.ForeignKey(Rental, on_delete=models.CASCADE, db_column='item_id', verbose_name="Инвентарь")
    size = models.ForeignKey('RentalSize', null=True, blank=True, on_delete=models.PROTECT, verbose_name="Размер")

    start_datetime = models.DateTimeField("Начало аренды")
    end_datetime = models.DateTimeField("Конец аренды")

    status = models.CharField(
        "Статус",
        max_length=20,
        choices=[
            ('booked', 'Забронирована'),
            ('active', 'В аренде'),
            ('awaiting_return', 'Ожидает возврата'),
            ('completed', 'Завершена'),
            ('cancelled', 'Отменена'),
        ],
        default='booked'
    )

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        db_table = 'user_rentals'
        
        verbose_name = "Аренда пользователя"
        verbose_name_plural = "Аренды пользователей"


# -----------------------------
# Уведомления
# -----------------------------
class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="Пользователь")
    type = models.CharField("Тип", max_length=50)
    text = models.TextField("Текст")
    link = models.CharField("Ссылка", max_length=255, blank=True, null=True)
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Дата создания")

    class Meta:
        managed = False
        db_table = 'notifications'
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return f"Уведомление для {self.user.username}"
class CartItem(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id')
    quantity = models.IntegerField(default=1)
    selected_size = models.CharField(max_length=10, null=True, db_column='selected_size')
   
    class Meta:
        db_table = 'cart_items'
        managed = False
# -----------------------------
# Заказы
# -----------------------------
# -----------------------------
# Заказы
# -----------------------------
class Orders(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id')

    pvz = models.CharField(max_length=255)
    pickup_time = models.CharField(max_length=255, null=True)
    comment = models.TextField(null=True)

    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'Новый'),
            ('processing', 'Готовится'),
            ('ready', 'Готов к выдаче'),
            ('completed', 'Завершён'),
        ],
        default='new'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders'
        managed = False


class OrderItems(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, db_column='order_id', related_name="items")
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id')

    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=10, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'order_items'
        managed = False
class RentalSize(models.Model):
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, related_name="sizes")
    size = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField(default=0)
    class Meta:
        db_table = 'rental_sizes'
        managed = False
    def __str__(self):
        return f"{self.rental.name} — {self.size} ({self.quantity})"

class ProductSize(models.Model):
    product = models.ForeignKey(Products, related_name="sizes", on_delete=models.CASCADE)
    size = models.CharField(max_length=10)
    quantity = models.IntegerField(default=0)

    class Meta:
        db_table = 'product_sizes'
        managed = False
