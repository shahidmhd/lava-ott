import datetime
import requests
from requests.auth import HTTPBasicAuth
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
import json

from .models import Transaction
from videos.models import Order
from django.conf import settings
from videos.utils import get_expiry_date

url_config = settings.PAYMENT_URL_CONFIG
config = settings.PAYMENT_CONFIG

USE_MOCK_API = False  # Toggle for mock/live

def mock_cachefree_api(endpoint, method='GET', **kwargs):
    """Mock CacheFree API responses for testing"""
    if method == 'POST' and 'orders' in endpoint:
        return {
            'status_code': 200,
            'json': {
                'id': f'order_mock_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}',
                'amount': kwargs.get('json', {}).get('amount', 10000),
                'amount_due': kwargs.get('json', {}).get('amount', 10000),
                'amount_paid': 0,
                'attempts': 0,
                'created_at': int(datetime.datetime.now().timestamp()),
                'currency': 'INR',
                'entity': 'order',
                'offer_id': None,
                'receipt': kwargs.get('json', {}).get('receipt', 'test_receipt'),
                'status': 'created'
            }
        }
    elif method == 'GET' and 'orders' in endpoint:
        return {
            'status_code': 200,
            'json': {'status': 'created'}
        }
    return {'status_code': 404, 'json': {'error': 'Not found'}}


class PaymentCheckoutBaseView(APIView):
    """Shared base for test and live checkout views"""

    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def handle_checkout(self, request, order_id):
        expiry = timezone.now() - timedelta(hours=12)
        for i in Transaction.objects.filter(status='created', timestamp__gte=expiry):
            try:
                if USE_MOCK_API:
                    mock_response = mock_cachefree_api(f'orders/{i.cachefree_order_id}', method='GET')
                    if mock_response['status_code'] == 200:
                        res = mock_response['json']
                        if res['status'] != i.status:
                            i.status = res['status']
                            i.save()
                else:
                    res = requests.get(
                        f'https://api.cachefree.com/v1/orders/{i.cachefree_order_id}',
                        auth=HTTPBasicAuth(config['key_id'], config['key_secret']),
                        timeout=10
                    )
                    res_data = res.json()
                    if res_data['status'] != i.status:
                        i.status = res_data['status']
                        i.save()
            except Exception as e:
                print(f"Error checking transaction {i.id}: {e}")
                continue

        try:
            order_id = self.get_order_id(order_id)
            try:
                order_obj = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                return JsonResponse({'message': 'Invalid Order'})

            amount = int(order_obj.subscription_amount)
            payload = {
                "amount": int(str(amount) + '00'),
                "currency": "INR",
                "receipt": Transaction.generate_receipt()
            }
            headers = {'Content-Type': 'application/json'}

            if USE_MOCK_API:
                print("Using Mock CacheFree API")
                mock_response = mock_cachefree_api('orders', method='POST', json=payload, headers=headers)
                response_status = mock_response['status_code']
                res_dict = mock_response['json']
            else:
                response = requests.post(
                    'https://api.cachefree.com/v1/orders',
                    json=payload, headers=headers,
                    auth=HTTPBasicAuth(config['key_id'], config['key_secret']),
                    timeout=30
                )
                response_status = response.status_code
                res_dict = response.json()

            if 'error' in res_dict:
                msg = res_dict['error'].get('description', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            transaction = Transaction.objects.create(
                razorpay_order_id=res_dict.get('id'),
                amount=amount,
                amount_due=res_dict.get('amount_due'),
                amount_paid=res_dict.get('amount_paid'),
                attempts=res_dict.get('attempts'),
                created_at=res_dict.get('created_at'),
                currency=res_dict.get('currency'),
                entity=res_dict.get('entity'),
                offer_id=res_dict.get('offer_id'),
                receipt=res_dict.get('receipt'),
                status=res_dict.get('status'),
                order=order_obj
            )

            res_dict = {
                'key_id': config['key_id'],
                'response_url': 'https://api.lavaott.com/payment/response/',
                'id': transaction.razorpay_order_id,
                'amount': amount,
                'currency': 'INR',
                'name': 'Lava OTT',
                'description': f'Subscription for Order #{order_obj.id}'
            }

            return render(request, 'checkout.html', context={'data': res_dict})
        except Exception as e:
            print(f"Checkout error: {e}")
            return JsonResponse({'message': str(e)})


class PaymentCheckoutTestView(PaymentCheckoutBaseView):
    """Test view using mock API"""
    def get(self, request, id):
        return self.handle_checkout(request, id)


class PaymentCheckoutView(PaymentCheckoutBaseView):
    """Live view (set USE_MOCK_API=False for real gateway)"""
    def get(self, request, id):
        return self.handle_checkout(request, id)


class PaymentResponseView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        print(f"Payment response received: {response_data}")

        if 'error[code]' in response_data:
            error_description = response_data.get('error[description]', 'Payment failed')
            razorpay_order_id = response_data.get('error[metadata][order_id]')
            try:
                if razorpay_order_id:
                    transaction = Transaction.objects.get(razorpay_order_id=razorpay_order_id)
                    transaction.status = 'failed'
                    transaction.payment_timestamp = datetime.datetime.now()
                    transaction.payment_id = response_data.get('error[metadata][payment_id]')
                    transaction.save()
            except Transaction.DoesNotExist:
                pass
            return render(request, 'error.html', {'err_msg': error_description})

        try:
            razorpay_order_id = response_data.get('razorpay_order_id')
            transaction = Transaction.objects.get(razorpay_order_id=razorpay_order_id)
            transaction.status = 'paid'
            transaction.payment_timestamp = datetime.datetime.now()
            transaction.payment_id = response_data.get('razorpay_payment_id')
            transaction.save()

            order = transaction.order
            new_start_date = timezone.now()
            order.status = 'completed'
            order.is_active = True
            order.start_date = new_start_date
            order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
            order.save()

            return render(request, 'success.html')
        except Transaction.DoesNotExist:
            return JsonResponse({'message': 'Invalid order ID'})


class PaymentResponseTestView(APIView):
    def post(self, request):
        return JsonResponse({'response': request.POST.dict()})
