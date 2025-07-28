from django.urls import path
from .views import *


urlpatterns = [
    path('login/', AdminLoginView.as_view()),
    path('status/', StatusView.as_view()),
    path('logout/', AdminLogoutView.as_view()),

    path('app/login/', AppLoginView.as_view()),
    path('app/login-otp-send/', AppLoginOTPSendView.as_view()),
    path('app/login-otp-verify/', AppLoginVerifyView.as_view()),

    path('otp-send/', OTPSendView.as_view()),
    path('delete-otp-verify/', UserDeleteOTPVerifyView.as_view()),

    path('list/', UserListView.as_view()),
    path('admin-user-search/', AdminUserSearchView.as_view()),
    path('admin-user-subscribe/', AdminUserSubscribeView.as_view()),
    path('admin-user-unsubscribe/', AdminUserUnsubscribeView.as_view()),
    path('app/delete/', UserDeleteView.as_view()),

    # Mobile App
    path('app/registration/', UserRegistrationView.as_view()),
    path('app/status/', UserStatusAppView.as_view()),
    path('app/profile/', UserProfileView.as_view()),
    path('app/profile-image-update/', UserProfileImageUpdateView.as_view()),
]

# Test
urlpatterns += [
    path('test/delete/', test_delete_view),
    path('setproject/', setproject),
    path('setadmin/', setadmin),

]
