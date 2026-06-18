from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Users, Profiles

@receiver(post_save, sender=Users)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profiles.objects.create(user=instance)
