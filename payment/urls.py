from django.urls import path
from .views import *

urlpatterns = [
    # Test
    path('checkout-test/<id>/', PaymentCheckoutTestView.as_view(), name='checkout-test'),
    # Live
    path('checkout/<id>/', PaymentCheckoutView.as_view(), name='checkout-test'),

    path('response/', PaymentResponseView.as_view(), name='response-test'),
]
