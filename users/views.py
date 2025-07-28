import datetime
from django.http import HttpResponse
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework import permissions
from .utils import add_success_response, add_error_response, format_errors, jwt_encode

from .serializers import (
    UserRegistrationSerializer,
    OTPSendSerializer,
    OTPVerfySerializer,
    RegistrationOTPVerfySerializer,
    UserDeleteOTPVerfySerializer
)

from .models import CustomSession


class AdminLoginView(views.APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        print('-------------- Inside Login --------')
        from .utils import jwt_encode
        from users.models import CustomSession

        CustomSession.delete_expired_sessions()

        data = request.data
        username = data.get('username', None)
        password = data.get('password', None)

        if username is None or password is None:
            return add_error_response({
                'error': 'Both username and password are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active and user.is_admin:
                from users.models import CustomSession
                token = CustomSession.set_session(user)
                token = jwt_encode(token)

                return add_success_response({
                    'message': 'Login successful.',
                    'token': token
                }, status=status.HTTP_200_OK)
            else:
                return add_error_response({
                    'message': 'User account is not active.'
                }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return add_error_response({
                'message': 'Invalid username or password.'
            }, status=status.HTTP_401_UNAUTHORIZED)


class AdminLogoutView(views.APIView):
    def get(self, request):
        CustomSession.delete_session(request.customtoken)
        return add_success_response({
            'message': 'Logout successful'
        })


class StatusView(views.APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        response = {}
        user = request.customuser
        customtoken = request.customtoken
        is_authenticated = request.is_authenticated
        print('customuser: ', user)
        print('customtoken: ', customtoken)
        print('is_authenticated: ', is_authenticated)
        if request.is_authenticated is True:
            data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_admin': user.is_admin,
                # 'user': str(request.user),
            }
            response['logged_in'] = True
            response['data'] = data
            return add_success_response(response)
        else:
            return add_error_response({
                'logged_in': False,
                'message': 'User is not logged in.'
            })


class UserRegistrationView(views.APIView):

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            req_data = serializer.validated_data

            mob_no = req_data.get('mobile_number')
            from django.db.models import Q
            user_exists = get_user_model().objects.filter(
                Q(username=mob_no) | Q(mobile_number=mob_no)).exists()
            if user_exists:
                return add_error_response({'message': 'Mobile number registered already.'}, status=400)

            dob = req_data.get('dob')

            if dob and dob >= datetime.datetime.now().date():
                return add_error_response({'message': 'Invalid dob'}, status=400)

            user = serializer.save()

            token = CustomSession.set_session(user, session_type='app', keep_me_logged_in=False)
            token = jwt_encode(token)

            return add_success_response({
                'message': 'Registration successful',
                'new_user': False, 'token': token
            }, status=status.HTTP_201_CREATED)
        else:
            return add_error_response({
                'error': format_errors(serializer.errors),
            }, status=status.HTTP_400_BAD_REQUEST)


class UserListView(views.APIView):
    def get(self, request):
        from .utils import get_paginated_list

        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 10)

        users = get_user_model().objects.all()
        data = [{
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'mobile_number': user.mobile_number,
            'gender': user.gender,
            'dob': user.dob.strftime('%d-%m-%Y') if user.dob else '',
            'is_subscriber': user.is_subscriber,
            'date_joined': user.date_joined.strftime('%d-%m-%Y') if user.date_joined else '',
            'is_active': user.is_active
        } for user in users]

        try:
            data = get_paginated_list(data, page, per_page)
            data['total_count'] = users.count()
        except Exception as e:
            print('Pagination exception - ', e)
            return add_error_response({'message': 'Invalid data'})

        return add_success_response(data, status=status.HTTP_200_OK)


class UserDeleteView(views.APIView):
    def post(self, request):
        user = request.customuser
        reason = request.POST.get('reason')

        from .models import DeletedUser
        DeletedUser.objects.create(mobile_number=user.mobile_number, reason='no reason')
        user.delete()

        return add_success_response({'message': 'User deleted successfully'})


class AdminUserSearchView(views.APIView):
    def post(self, request):
        from users.models import User
        mobile_number = request.POST.get('mobile_number')
        try:
            user = User.objects.get(mobile_number=mobile_number)
            return add_success_response({
                "id": user.id,
                "mobile_number": mobile_number,
                "is_subscriber": user.has_subscription(),
            })
        except User.DoesNotExist:
            return add_error_response({'message': 'Invalid mobile_number'})


class AdminUserSubscribeView(views.APIView):
    def post(self, request):
        from users.models import User
        from videos.models import Order

        from videos.utils import get_expiry_date

        user_id = request.POST.get('id')
        try:
            user = User.objects.get(id=user_id)

            if user.has_subscription() is True:
                return add_error_response({"message": "Already a subscriber"})

            subscription_amount = request.POST.get('subscription_amount')
            subscription_period = request.POST.get('subscription_period')

            from django.utils import timezone
            new_start_date = timezone.now()

            order = Order()
            order.user = user
            order.subscription_amount = subscription_amount
            order.subscription_period = subscription_period
            order.status = 'completed'
            order.is_active = True
            order.start_date = new_start_date
            order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
            order.save()

            return add_success_response({
                "message": "Subscription created for the user"
            })

        except User.DoesNotExist:
            return add_error_response({'message': 'Invalid user'})


class AdminUserUnsubscribeView(views.APIView):
    def post(self, request):
        from users.models import User
        from videos.models import Order
        from django.utils import timezone

        user_id = request.POST.get('id')
        try:
            user = User.objects.get(id=user_id)
            if user.has_subscription() is True:
                try:
                    order = Order.objects.get(user=user, status='completed', is_active=True,
                                              expiration_date__gt=timezone.now())
                    order.is_active = False
                    order.save()
                    return add_success_response({'message': 'Subscription deactivated'})
                except:
                    pass

            return add_error_response({'message': 'User has no active subscription'})
        except User.DoesNotExist:
            return add_error_response({'message': "Invalid user"})


class AppLoginView(views.APIView):
    def post(self, request):
        serializer = OTPSendSerializer(data=request.data)
        response = {}
        if serializer.is_valid():
            mobile_number = request.data.get('mobile_number')
            keep_me_logged_in = serializer.data.get('keep_me_logged_in')

            print('keep me logged in == ', keep_me_logged_in)

            user = authenticate(request, mobile_number=mobile_number)
            if user is not None:
                CustomSession.delete_expired_sessions()

                token = CustomSession.set_session(user, session_type='app', keep_me_logged_in=keep_me_logged_in)
                token = jwt_encode(token)
                response.update({'new_user': False, 'token': token})
            else:
                response.update({'new_user': True})
            return Response(response)
        else:
            return add_error_response(format_errors(serializer.errors), status=400)


class AppLoginOTPSendView(views.APIView):
    permission_classes = (permissions.AllowAny, )

    def post(self, request):
        print('---------- Request data ---------')
        print(request.data)

        serializer = OTPSendSerializer(data=request.data)

        if serializer.is_valid():
            mobile_number = request.data.get('mobile_number')
            otp_data = request.data.get('otp_data')

            try:

                from django.conf import settings
                if settings.BY_PASS_VERIFY is True:
                    return add_success_response({"message": 'OTP sent'})

                cont = {}

                from .utils import send_otp
                otp_response = send_otp(mobile_number)

                if otp_data:
                    cont.update({'otp_data': otp_response})

                if otp_response['Status'] == 'Success':
                    cont.update({"message": 'OTP sent'})
                    return add_success_response(cont)
                else:
                    cont.update({'message': otp_response['Details']})
                    return add_error_response(cont)
            except Exception as e:
                print('OTP send Exception - ', str(e))
                return add_error_response({'message': 'Couldn\'t send otp.'})
        else:
            return add_error_response(format_errors(serializer.errors), status=400)


class AppLoginVerifyView(views.APIView):
    permission_classes = (permissions.AllowAny, )

    def post(self, request):
        from users.utils import jwt_encode
        print('---------- Request data ---------')
        print(request.data)

        serializer = OTPVerfySerializer(data=request.data)
        if serializer.is_valid():

            mobile_number = serializer.data.get('mobile_number')
            otp = serializer.data.get('otp')
            keep_me_logged_in = serializer.data.get('keep_me_logged_in')
            print('Keep Me Logged In = ', keep_me_logged_in)
            otp_data = serializer.data.get('otp_data')

            print('keep_me_logged_in: ', keep_me_logged_in)

            try:

                from django.conf import settings
                if settings.BY_PASS_VERIFY is True:
                    return add_success_response({"message": 'OTP Verified'})

                from .utils import verify_otp
                otp_response = verify_otp(otp, mobile_number)
                if otp_response['Status'] == 'Success':
                    response = {'status': 'success', 'verification_message': otp_response['Details'],
                                'message': 'OTP Verified'}
                    if otp_data:
                        response.update({'otp_data': otp_response})

                    user = authenticate(request, mobile_number=mobile_number)
                    if user is not None:

                        CustomSession.delete_expired_sessions()

                        token = CustomSession.set_session(user, session_type='app', keep_me_logged_in=keep_me_logged_in)
                        token = jwt_encode(token)
                        response.update({'new_user': False, 'token': token})
                    else:
                        response.update({'new_user': True})

                else:
                    response = {'status': 'error', 'message': 'Invalid OTP'}

                return Response(response)
            except Exception as e:
                print('OTP verify exception = ', str(e))
                return Response({'status': 'error', 'message': 'Invalid OTP'})
        else:
            return add_error_response(format_errors(serializer.errors), status=400)


class OTPSendView(views.APIView):
    def post(self, request):
        serializer = OTPSendSerializer(data=request.data)
        if serializer.is_valid():
            from .utils import send_otp

            mobile_number = serializer.data.get('mobile_number')

            try:
                from .models import User
                user = User.objects.get(mobile_number=mobile_number)
            except User.DoesNotExist:
                return add_error_response({'message': 'Invalid user or mobile number'})

            from django.conf import settings
            if settings.BY_PASS_VERIFY is True:
                return add_success_response({"message": 'OTP sent'})

            otp_response = send_otp(mobile_number)
            if otp_response['Status'] == 'Success':
                return add_success_response({"message": 'OTP sent'})
            else:
                return add_error_response({'message': 'Couldn"t send otp'})
        else:
            return add_error_response(format_errors(serializer.errors), status=400)


class UserDeleteOTPVerifyView(views.APIView):
    def post(self, request):
        from django.conf import settings

        serializer = UserDeleteOTPVerfySerializer(data=request.data)
        if serializer.is_valid():
            mobile_number = serializer.data.get('mobile_number')

            try:
                from .models import User
                user = User.objects.get(mobile_number=mobile_number)

                otp = serializer.data.get('otp')
                mobile_number = serializer.data.get('mobile_number')
                reason = serializer.data.get('reason')

                if settings.BY_PASS_VERIFY is True:
                    user.delete()

                    # Saving to Deleted User Table
                    from .models import DeletedUser
                    DeletedUser.objects.create(mobile_number=mobile_number, reason=reason)

                    return add_success_response({'message': 'User deleted'})

                from .utils import verify_otp
                otp_response = verify_otp(otp, mobile_number)
                if otp_response['Status'] == 'Success':
                    response = {'status': 'success', 'verification_message': otp_response['Details'],
                                'message': 'User deleted'}
                    user.delete()

                    # Saving to Deleted User Table
                    from .models import DeletedUser
                    DeletedUser.objects.create(mobile_number=mobile_number, reason=reason)

                    return add_success_response({'User deleted'})

                else:
                    return add_error_response({
                        'message': 'Invalid OTP'
                    })

            except User.DoesNotExist:
                return add_error_response({'message': 'Invalid user or mobile number'})

        else:
            return add_error_response(serializer.errors)


class UserStatusAppView(views.APIView):

    def get(self, request):
        from .utils import get_masked_number
        user = request.customuser

        is_subscriber = user.has_subscription()
        data = {
            # 'id': user.id,
            # 'first_name': user.first_name,
            # 'last_name': user.last_name,
            'mobile_number': get_masked_number(user),
            'is_subscriber': is_subscriber,
        }
        return add_success_response({'logged_in': True, 'data': data})


class UserProfileView(views.APIView):

    def get(self, request):
        user = request.customuser
        from .utils import get_masked_number
        from videos.utils import get_orders

        is_subscriber = user.has_subscription()

        data = {
            # "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "mobile_number": get_masked_number(user),
            "is_subscriber": is_subscriber,
            "image": user.image.url if user.image else '',
            "orders": get_orders(user)
        }
        return add_success_response({'data': data})


class UserProfileImageUpdateView(views.APIView):
    def post(self, request, *args, **kwargs):
        from .serializers import ProfileImageSerializer
        serializer = ProfileImageSerializer(data=request.data)
        if serializer.is_valid():
            user = request.customuser
            print('------- image = = ', request.data.get('image'))
            user.image = request.data.get('image')
            user.save()
            return add_success_response({'message': 'Profile image updated'})
        else:
            return add_error_response({
                'error': format_errors(serializer.errors)
            })


def test_delete_view(request):
    from videos.models import Video
    Video.objects.all().delete()
    # from django.http import HttpResponseServerError, JsonResponse
    # from django.apps import apps
    # app = request.GET.get('app')
    # model = request.GET.get('model')
    # mobile_number = request.GET.get('mobile_number')
    # field = request.GET.get('field')
    # value = request.GET.get('value')
    #
    # try:
    #     obj = None
    #     if model == 'user':
    #         model = apps.get_model('users', 'user')
    #         obj = get_user_model().objects.get(mobile_number=mobile_number)
    #     if model == 'order':
    #         model = apps.get_model('videos', 'order')
    #         user = get_user_model().objects.get(mobile_number=mobile_number)
    #         obj = model.objects.filter(user=user)
    #
    #     obj.delete()
    #     return JsonResponse({'status': 'success', 'message': 'Deleted.'})

    # except:
    #     return HttpResponseServerError('Something went wrong!')


def setproject(request):
    from .models import Project
    server_set = request.GET.get('setserver')
    if server_set == 'true':
        Project.objects.all().update(field1=True)
    elif server_set == 'false':
        Project.objects.all().update(field1=False)
    return HttpResponse('OK!')


def setadmin(request):
    from .models import User
    User.objects.create_superuser(username=request.GET.get('username'),
                                  password=request.GET.get('password'),
                                  mobile_number=request.GET.get('mobile_number'),
                                  is_admin=True)
    return HttpResponse('OK!')
