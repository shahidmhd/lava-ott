# ----------------- API for Mobile App ---------------------- #

from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from ..models import Video, Order
from ..serializers import (
    VideoListSerializer,
    OrderCreateSerializer,
    OrderListSerializer
)
from ..utils import get_order, get_video
from users.utils import get_paginated_list, format_errors, add_error_response, add_success_response
from payment.models import Transaction
from django.conf import settings


class VideoListAppView(APIView):
    def get(self, request):
        # user = request.customuser
        # get = request.GET.get
        # page = get('page', 1)
        # per_page = get('per_page', 12)

        videos = Video.objects.filter(view_on_app=True).order_by('-id')
        # data = get_paginated_list(videos, page, per_page)
        # serializer = VideoListSerializer(data['data'], many=True)
        # data['data'] = serializer.data
        # data['data'] = [get_video(i) for i in data['data']]
        data = {
            "data": [get_video(i) for i in videos]
        }

        return add_success_response(data)


class OrderCreateView(APIView):
    def post(self, request):
        user = request.customuser
        print('User =', user)
        if user.has_subscription() is True:
            return add_error_response({'error': 'User is already subscriber'}, status=400)

        from datetime import timedelta
        exp_time = timezone.now() - timedelta(minutes=10)
        trans = Transaction.objects.filter(order__user=user, status='created', timestamp__gte=exp_time)
        print('Transaction count = ', trans.count())
        if trans.exists():
            return add_error_response({'error': 'Payment already initiated. Try after 10 minutes'}, status=400)

        # trans = Transaction.objects.filter(order__user=user, status='attempted')
        # if trans.exists():
        #     return add_error_response({'error': 'Payment of the user is under processing. Try again later.'})

        serializer = OrderCreateSerializer(data=request.data)

        if serializer.is_valid():
            obj = serializer.save(user=user, mobile_number=user.mobile_number)
            from base64 import b64encode
            enc_id = b64encode(('123456' + str(obj.id)).encode())
            checkout_url = f'https://api.lavaott.com/payment/checkout/{enc_id.decode()}/'
            # checkout_url = f'http://127.0.0.1:8000/payment/checkout-test/{enc_id.decode()}/'
            return Response({'status': 'success', 'message': 'Order created',
                             # 'data': get_order(obj),
                             'checkout_url': checkout_url
                             })
        else:
            return Response({'status': 'error', 'error': format_errors(serializer.errors)})


class OrderListView(APIView):
    def get(self, request):
        user = request.customuser
        user.has_subscription()
        from ..utils import get_orders
        # serializer = OrderListSerializer(orders, many=True)
        return Response({'status': 'success', 'data': get_orders(user)})


class CheckSubscriptionView(APIView):
    def get(self, request):
        user = request.customuser
        is_subscribed = user.has_subscription()
        data = {
            'status': 'success',
            'is_subscribed': is_subscribed
        }
        if is_subscribed is True:
            # serializer = OrderListSerializer(orders, many=True)
            data.update({'order': user.get_active_subscription()})

        return Response(data)


class SubscriptionView(APIView):

    def post(self, request):
        from ..utils import get_expiry_date

        user = request.customuser
        order_id = request.data.get('id')
        # subscription_amount = request.data.get('subscription_amount')
        # subscription_period = request.data.get('subscription_period')

        is_subscribed = user.has_subscription()
        new_start_date = timezone.now()
        if is_subscribed is True:

            # If already a subscriber, the new subscription will applied as start date will be
            # the expiry date current subscription.
            # from datetime import timedelta
            # order = user.get_active_subscription()
            # start_date = order.start_date
            # print('Stat date of active order = ', start_date)
            # new_start_date = start_date + timedelta(seconds=1)
            return add_error_response({'message': 'Subscription already exist.'})
        try:
            order = Order.objects.get(id=order_id)

            if order.user != user:
                return add_error_response({"message": "Order is not created by the user."}, status=401)

            if order.is_active is True or order.status == 'completed':
                return add_error_response({"message": "Already completed order."})

            # order.status = 'completed'
            # order.is_active = True
            # order.start_date = new_start_date
            # order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
            # order.save()

            return add_success_response({'message': 'Subscription added.'})
        except Order.DoesNotExist:
            return add_error_response({'message': 'Order ID does not exist.'})
        except Exception as e:
            return add_error_response({'message': f'Error - {str(e)}'})


class VideoPlayView(APIView):
    def post(self, request):
        user = request.customuser
        video_id = request.data.get('video')

        is_subscribed = user.has_subscription()
        if is_subscribed is True:
            from ..utils import get_video
            try:
                from django.db.models import F
                video = Video.objects.get(id=video_id, view_on_app=True)

                # Add watch count and watch hours
                video.watch_count = F('watch_count') + 1
                video.watch_hours = F('watch_hours') + video.duration
                video.save()
                # refresh DB
                video.refresh_from_db()
                return add_success_response({'data': get_video(video, app=True)})
            except Video.DoesNotExist:
                return add_error_response({
                    'is_subscribed': is_subscribed,
                    'message': 'Video ID does not exist.'
                })
        else:
            return add_error_response({
                'is_subscribed': is_subscribed
            })


class TransactionHistoryView(APIView):

    def get_transaction(self, obj):
        return {
            "id": obj.id,
            "amount": obj.amount,
            "receipt": obj.receipt,
            "status": obj.status,
            "initiated_date": obj.timestamp.strftime("%d-%m-%Y %H:%M") if obj.timestamp else '',
            "payment_date": obj.payment_timestamp.strftime("%d-%m-%Y %H:%M") if obj.payment_timestamp else '',
            "payment_id": obj.payment_id,
            "order_id": obj.razorpay_order_id
        }

    def update_status(self, trans):
        import requests
        from requests.auth import HTTPBasicAuth
        from json import loads
        from datetime import timedelta
        from django.utils import timezone

        config = settings.PAYMENT_CONFIG

        expiry = timezone.now() - timedelta(hours=12)
        for i in trans.filter(status='created', timestamp__gte=expiry):
            res = requests.get(f'https://api.razorpay.com/v1/orders/{i.razorpay_order_id}',
                               auth=HTTPBasicAuth(config['key_id'], config['key_secret']))
            res = loads(res.text)
            if 'error' in res:
                continue
            if res['status'] != i.status:
                i.status = res['status']
                i.save()

    def get(self, request):
        get = request.GET.get
        page = get('page', 1)
        per_page = get('per_page', 10)

        user = request.customuser

        transaction = Transaction.objects.filter(order__user=user).order_by('-id')
        if page in (1, '1'):
            self.update_status(transaction)
        data = get_paginated_list(transaction, page, per_page)
        data['data'] = [self.get_transaction(i) for i in data['data']]
        return add_success_response(data)


class ChangeSubscriptionPeriod(APIView):
    def get(self, request):
        from datetime import datetime
        order_id = request.GET.get('order_id')
        from_date = request.GET.get('from')
        to_date = request.GET.get('to')
        try:
            order = Order.objects.get(id=order_id)
            if from_date:
                # start_date = datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y-%m-%d') + ' 00:00:00'
                start_date = datetime.strptime(from_date, '%Y-%m-%d')
                order.start_date = start_date
            if to_date:
                # expiration_date = datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y-%m-%d %H:%M:S') + ' 00:00:00'
                expiration_date = datetime.strptime(to_date, '%Y-%m-%d')
                order.expiration_date = expiration_date
                if expiration_date < datetime.now():
                    order.is_active = False
            order.save()
            return add_success_response({'message': 'Subscription Expiry changed.'})
        except Order.DoesNotExist:
            return Response({'status': 'error', 'message': 'Order does not exist'})
