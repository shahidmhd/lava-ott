from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone


class Video(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()

    thumbnail = models.ImageField(upload_to='thumbnails/')
    trailer = models.FileField(upload_to='trailers')
    file = models.FileField(upload_to='videos')

    director = models.CharField(max_length=100)
    cast = models.TextField()

    watch_count = models.PositiveIntegerField(default=0)
    view_on_app = models.BooleanField(default=False)
    watch_hours = models.FloatField(default=0)
    duration = models.FloatField(blank=True, null=True)
    delete_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)

    def delete(self, *args, **kwargs):
        from pathlib import Path

        file_path = Path(self.file.path)
        trailer_path = Path(self.trailer.path)
        thumbnail_path = Path(self.thumbnail.path)

        if trailer_path.exists():
            trailer_path.unlink()
        if file_path.exists():
            file_path.unlink()
        if thumbnail_path.exists():
            thumbnail_path.unlink()

        super().delete(*args, **kwargs)


class Order(models.Model):
    STATUS_CHOICES = [('pending', 'pending'), ('completed', 'completed')]

    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    mobile_number = models.CharField(max_length=100, blank=True, null=True)

    subscription_amount = models.FloatField()
    subscription_period = models.CharField(max_length=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(default=timezone.now)

    start_date = models.DateTimeField(null=True)
    expiration_date = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=False)


class SubscriptionPlan(models.Model):
    SUB_PERIOD_CHOICES = [('month', 'month'), ('year', 'year')]

    subscription_amount = models.FloatField()
    subscription_period = models.CharField(max_length=10, choices=SUB_PERIOD_CHOICES)


class Carousel(models.Model):
    image = models.ImageField(upload_to='carousel')

    def delete(self, *args, **kwargs):
        from pathlib import Path
        image_path = Path(self.image.path)

        if image_path.exists():
            image_path.unlink()

        super().delete(*args, **kwargs)
