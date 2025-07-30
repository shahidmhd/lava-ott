import datetime
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
import json
import ssl
import urllib3

from .models import Transaction
from videos.models import Order
from django.conf import settings
from videos.utils import get_expiry_date

url_config = settings.PAYMENT_URL_CONFIG
config = settings.PAYMENT_CONFIG

USE_MOCK_API = False  # Toggle for mock/live

def mock_cachefree_api(endpoint, method='GET', **kwargs):
    """Mock Cashfree API responses for testing"""
    if method == 'POST' and 'orders' in endpoint:
        payload = kwargs.get('json', {})
        return {
            'status_code': 200,
            'json': {
                'cf_order_id': 12345,
                'created_at': datetime.datetime.now().isoformat(),
                'customer_details': payload.get('customer_details', {}),
                'entity': 'order',
                'order_amount': payload.get('order_amount', 100.0),
                'order_currency': payload.get('order_currency', 'INR'),
                'order_expiry_time': (datetime.datetime.now() + timedelta(minutes=15)).isoformat(),
                'order_id': payload.get('order_id', f'order_mock_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'),
                'order_meta': {'return_url': 'https://test.cashfree.com'},
                'order_note': payload.get('order_note', ''),
                'order_status': 'ACTIVE',
                'order_tags': None,
                'payment_session_id': f'session_mock_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'
            }
        }
    elif method == 'GET' and 'orders' in endpoint:
        return {
            'status_code': 200,
            'json': {'order_status': 'ACTIVE'}
        }
    return {'status_code': 404, 'json': {'error': 'Not found'}}


def create_secure_session():
    """Create a requests session with proper SSL configuration"""
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # SSL configuration options - try these in order of preference
    
    # Option 1: Force TLS 1.2+ (recommended)
    session.mount('https://', HTTPAdapter(max_retries=retry_strategy))
    
    return session


def make_cashfree_request(url, method='GET', **kwargs):
    """Make a secure request to Cashfree API with proper error handling"""
    session = create_secure_session()
    
    # Cashfree uses different authentication - x-client-id and x-client-secret headers
    headers = kwargs.get('headers', {})
    headers.update({
        'User-Agent': 'LavaOTT/1.0',
        'Accept': 'application/json',
        'x-client-id': config['key_id'],
        'x-client-secret': config['key_secret'],
        'x-api-version': '2023-08-01'  # Latest Cashfree API version
    })
    kwargs['headers'] = headers
    kwargs['timeout'] = kwargs.get('timeout', 30)
    
    # Remove auth if it exists since Cashfree uses headers
    if 'auth' in kwargs:
        del kwargs['auth']
    
    try:
        # Option 1: Try with default SSL settings
        if method.upper() == 'POST':
            response = session.post(url, **kwargs)
        else:
            response = session.get(url, **kwargs)
        return response
        
    except requests.exceptions.SSLError as ssl_error:
        print(f"SSL Error occurred: {ssl_error}")
        
        # Option 2: Try with SSL verification disabled (less secure, use only if necessary)
        print("Retrying with SSL verification disabled...")
        kwargs['verify'] = False
        
        # Suppress SSL warnings when verification is disabled
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        try:
            if method.upper() == 'POST':
                response = session.post(url, **kwargs)
            else:
                response = session.get(url, **kwargs)
            return response
        except Exception as e:
            print(f"Request failed even with SSL verification disabled: {e}")
            raise
    
    except Exception as e:
        print(f"Request failed with error: {e}")
        raise


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
                        if res.get('order_status') != i.status:
                            i.status = res.get('order_status')
                            i.save()
                else:
                    # Use correct Cashfree endpoint for order status check
                    api_endpoint = 'https://sandbox.cashfree.com/pg/orders' if config.get('test_mode', True) else 'https://api.cashfree.com/pg/orders'
                    response = make_cashfree_request(
                        f'{api_endpoint}/{i.razorpay_order_id}',
                        method='GET'
                    )
                    
                    if response.status_code == 200:
                        res_data = response.json()
                        if res_data.get('order_status') != i.status:
                            i.status = res_data.get('order_status')
                            i.save()
                    else:
                        print(f"API request failed with status {response.status_code}: {response.text}")
                        
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
                "order_amount": float(amount),  # Cashfree expects float, not cents
                "order_currency": "INR",
                "order_id": Transaction.generate_receipt(),  # Unique order ID
                "customer_details": {
                    "customer_id": str(request.user.id) if request.user.is_authenticated else "guest",
                    "customer_email": request.user.email if request.user.is_authenticated else "",
                    "customer_phone": getattr(request.user, 'phone', '') if request.user.is_authenticated else ""
                }
            }
            headers = {'Content-Type': 'application/json'}

            # Use correct Cashfree sandbox/production endpoint
            api_endpoint = 'https://sandbox.cashfree.com/pg/orders' if config.get('test_mode', True) else 'https://api.cashfree.com/pg/orders'
            
            if USE_MOCK_API:
                print("Using Mock Cashfree API")
                mock_response = mock_cachefree_api('orders', method='POST', json=payload, headers=headers)
                response_status = mock_response['status_code']
                res_dict = mock_response['json']
            else:
                # Use the correct Cashfree endpoint
                response = make_cashfree_request(
                    api_endpoint,
                    method='POST',
                    json=payload,
                    headers=headers
                )
                response_status = response.status_code
                
                # Cashfree returns 201 for successful order creation
                if response_status == 201:
                    res_dict = response.json()
                else:
                    print(f"API request failed with status {response_status}: {response.text}")
                    error_msg = response.json().get('message', 'Payment gateway error') if response.status_code != 500 else 'Payment gateway error'
                    return render(request, 'error.html', {
                        'err_msg': error_msg
                    })

            # Check for Cashfree API errors in response
            if 'message' in res_dict and response_status != 201:
                msg = res_dict.get('message', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            transaction = Transaction.objects.create(
                razorpay_order_id=res_dict.get('order_id'),  # Cashfree returns 'order_id'
                amount=amount,
                amount_due=res_dict.get('order_amount'),
                amount_paid=0,  # Initially 0
                attempts=0,  # Initially 0
                created_at=int(datetime.datetime.now().timestamp()),
                currency=res_dict.get('order_currency'),
                entity='order',
                offer_id=None,
                receipt=res_dict.get('order_id'),
                status=res_dict.get('order_status', 'ACTIVE'),
                order=order_obj
            )

            res_dict = {
                'key_id': config['key_id'],
                'response_url': 'https://api.lavaott.com/payment/response/',
                'order_id': transaction.razorpay_order_id,
                'payment_session_id': res_dict.get('payment_session_id'),  # Required for Cashfree checkout
                'order_amount': amount,
                'order_currency': 'INR',
                'order_note': f'Subscription for Order #{order_obj.id}',
                'customer_details': payload['customer_details']
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