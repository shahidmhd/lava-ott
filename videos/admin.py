from django.contrib import admin

from .models import Video, Order, SubscriptionPlan, Carousel

# admin.site.register(Video)
admin.site.register(Order)
# admin.site.register(SubscriptionPlan)
admin.site.register(Carousel)
