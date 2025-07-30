from django.shortcuts import render
import requests
from requests.auth import HTTPBasicAuth

from rest_framework.views import APIView
from rest_framework.response import Response
import datetime
from django.http import JsonResponse

from .models import Transaction
from videos.models import Order
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
import json

url_config = settings.PAYMENT_URL_CONFIG
config = settings.PAYMENT_CONFIG

# Add this flag to enable mock mode for testing
USE_MOCK_API = False  # Set to False when you have the real CacheFree API

def mock_cachefree_api(endpoint, method='GET', **kwargs):
    """Mock CacheFree API responses for testing"""
    if method == 'POST' and 'orders' in endpoint:
        # Mock order creation response
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
        # Mock order status response
        return {
            'status_code': 200,
            'json': {
                'status': 'created'
            }
        }
    
    return {'status_code': 404, 'json': {'error': 'Not found'}}

class PaymentCheckoutTestView(APIView):
    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def get(self, request, **kwargs):
        config = self.get_key_config()
        expiry = timezone.now() - timedelta(hours=12)
        
        # Handle existing transactions with better error handling
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
                    res = requests.get(f'https://api.cachefree.com/v1/orders/{i.cachefree_order_id}',
                                       auth=HTTPBasicAuth(config['key_id'], config['key_secret']),
                                       timeout=10)
                    res_data = res.json()
                    if res_data['status'] != i.status:
                        i.status = res_data['status']
                        i.save()
            except Exception as e:
                print(f"Error checking transaction {i.id}: {e}")
                continue

        try:
            order_id = kwargs.get('id')
            order_id = self.get_order_id(order_id)

            try:
                order_obj = Order.objects.get(id=order_id)
            except:
                return JsonResponse({'message': 'Invalid Order'})

            exp_time = timezone.now() - timedelta(minutes=10)
            trans = Transaction.objects.filter(order=order_obj, timestamp__gte=exp_time)

            trans = Transaction.objects.filter(order=order_obj, status='attempted')

            amount = int(order_obj.subscription_amount)

            payload = {
                "amount": int(str(amount) + '00'),
                "currency": "INR",
                "receipt": Transaction.generate_receipt()
            }
            
            headers = {'Content-Type': 'application/json'}
            config = self.get_key_config()
            
            # Use mock API or real API based on flag
            if USE_MOCK_API:
                print("Using Mock CacheFree API for testing")
                mock_response = mock_cachefree_api('orders', method='POST', json=payload, headers=headers)
                response_status = mock_response['status_code']
                res_dict = mock_response['json']
                print(f"Mock API Response: {res_dict}")
            else:
                response = requests.post('https://api.cachefree.com/v1/orders',
                                         json=payload, headers=headers,
                                         auth=HTTPBasicAuth(config['key_id'], config['key_secret']),
                                         timeout=30)
                response_status = response.status_code
                res_dict = response.json()

            print('------------- Checkout Response ------------')
            print('status code : ', response_status)
            print('response : ', res_dict)
            print('------------- Checkout Response End ------------')

            # Error Response
            if 'error' in res_dict:
                msg = res_dict['error']['description'] if 'description' in res_dict['error'] else 'Payment gateway error'
                return render(request, 'error.html', {'err_msg': msg})

            order_id = res_dict.get('id')

            # Save to Transaction Table
            transaction = Transaction()
            transaction.razorpay_order_id = res_dict.get('id')
            transaction.amount = amount
            transaction.amount_due = res_dict.get('amount_due')
            transaction.amount_paid = res_dict.get('amount_paid')
            transaction.attempts = res_dict.get('attempts')
            transaction.created_at = res_dict.get('created_at')
            transaction.currency = res_dict.get('currency')
            transaction.entity = res_dict.get('entity')
            transaction.offer_id = res_dict.get('offer_id')
            transaction.receipt = res_dict.get('receipt')
            transaction.status = res_dict.get('status')
            transaction.order = order_obj
            transaction.save()
            
            config = self.get_key_config()
            res_dict = {
                'key_id': config['key_id'],
                'response_url': 'http://127.0.0.1:8000/payment/response/',
                'id': order_id,
                'amount': amount,
                'currency': 'INR',
                'name': 'Lava OTT',
                'description': f'Subscription for Order #{order_obj.id}'
            }
            print(res_dict)

            return render(self.request, 'checkout.html', context={'data': res_dict})
        except Exception as e:
            print(f"Checkout error: {e}")
            return JsonResponse({'message': str(e)})


class PaymentCheckoutView(PaymentCheckoutTestView):
    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def get(self, request, **kwargs):
        # Same logic as test view but for production
        # You can modify USE_MOCK_API to False when ready for production
        return super().get(request, **kwargs)


class PaymentResponseView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        print(f"Payment response received: {response_data}")

        # Payment Failed
        if 'error[code]' in response_data:
            error_description = response_data.get('error[description]', 'Payment failed')
            error_metadata = response_data.get('error[metadata]', '{}')
            
            try:
                error_metadata = json.loads(error_metadata)
                razorpay_payment_id = error_metadata.get('payment_id')
                razorpay_order_id = error_metadata.get('order_id')
            except:
                razorpay_payment_id = None
                razorpay_order_id = None

            if razorpay_order_id:
                try:
                    transaction = Transaction.objects.get(razorpay_order_id=razorpay_order_id)
                    transaction.status = 'failed'
                    transaction.payment_timestamp = datetime.datetime.now()
                    transaction.payment_id = razorpay_payment_id
                    transaction.save()
                except Transaction.DoesNotExist:
                    pass

            return render(request, 'error.html', {'err_msg': error_description})

        # Payment Success
        else:
            from django.utils import timezone
            from videos.utils import get_expiry_date

            razorpay = response_data.get('razorpay_payment_id')
            razorpay_order_id = response_data.get('razorpay_order_id')
            razorpay_signature = response_data.get('razorpay_signature')
            
            try:
                transaction = Transaction.objects.get(razorpay_order_id=razorpay_order_id)
                transaction.status = 'paid'
                transaction.payment_timestamp = datetime.datetime.now()
                transaction.payment_id = razorpay_payment_id
                transaction.save()

                new_start_date = timezone.now()
                order = transaction.order
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
        response_data = request.POST.dict()
        return JsonResponse({'response': response_data})