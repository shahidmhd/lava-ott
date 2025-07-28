from django.urls import path
from .views import *

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Carousel
    path('carousel-create/', carousel_create, name='carousel-create'),
    path('carousel-list/', carousel_list, name='carousel-list'),

    # Subscription Plan
    path('subscription-plan/create/', subscription_plan_create, name='subscription-plan-create'),
    path('subscription-plan/list/', subscription_plan_list, name='subscription-plan-list'),
    path('subscription-plan/delete/', subscription_plan_delete, name='subscription-plan-delete'),

    # Video
    path('video-create/', VideoCreateView.as_view(), name='video-create'),
    path('video-list/', VideoListView.as_view(), name='video-list'),
    path('video-delete/', VideoDeleteView.as_view(), name='video-delete'),
]

# Mobile App
urlpatterns += [
    path('app-subscription-plan/list/', subscription_plan_app_list, name='app-subscription-plan-list'),

    path('app-video-list/', VideoListAppView.as_view(), name='app-video-list'),
    path('app-order-create/', OrderCreateView.as_view(), name='app-order-create'),
    path('app-order-list/', OrderListView.as_view(), name='app-order-list'),
    path('app-check-subscription/', CheckSubscriptionView.as_view(), name='app-check-subscription'),
    path('app-subscription-create/', SubscriptionView.as_view(), name='app-subscription-create'),
    path('app-video-play/', VideoPlayView.as_view(), name='app-video-play'),
    path('app-transaction-history/', TransactionHistoryView.as_view(), name='app-transaction-history'),
    # test
    path('app-change-order-period/', ChangeSubscriptionPeriod.as_view(), name='app-change-order-period'),
]
# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# handler404 = 'users.error_handler_views.error_404_view'
