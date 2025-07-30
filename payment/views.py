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

def mock_cashfree_api(endpoint, method='GET', **kwargs):
    """Mock Cashfree API responses for testing"""
    if method == 'POST' and 'orders' in endpoint:
        payload = kwargs.get('json', {})
        # Use the order_id from the payload (this comes from Transaction.generate_receipt())
        mock_order_id = payload.get('order_id', f'order_mock_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}')
        return {
            'status_code': 201,  # Cashfree returns 201 for successful order creation
            'json': {
                'cf_order_id': 12345,
                'created_at': datetime.datetime.now().isoformat(),
                'customer_details': payload.get('customer_details', {}),
                'entity': 'order',
                'order_amount': payload.get('order_amount', 100.0),
                'order_currency': payload.get('order_currency', 'INR'),
                'order_expiry_time': (datetime.datetime.now() + timedelta(minutes=15)).isoformat(),
                'order_id': mock_order_id,  # Use the same order_id from the request
                'order_meta': {'return_url': 'http://127.0.0.1:8000/payment/response/'},
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
    
    return session


def make_cashfree_request(url, method='GET', **kwargs):
    """Make a secure request to Cashfree API with proper error handling"""
    session = create_secure_session()
    
    # Cashfree authentication headers
    headers = kwargs.get('headers', {})
    headers.update({
        'User-Agent': 'LavaOTT/1.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'x-client-id': config['key_id'],
        'x-client-secret': config['key_secret'],
        'x-api-version': '2023-08-01'  # Cashfree requires API version
    })
    kwargs['headers'] = headers
    kwargs['timeout'] = kwargs.get('timeout', 30)
    
    # Remove auth if it exists since Cashfree uses headers
    if 'auth' in kwargs:
        del kwargs['auth']
    
    try:
        if method.upper() == 'POST':
            response = session.post(url, **kwargs)
        else:
            response = session.get(url, **kwargs)
        return response
        
    except requests.exceptions.SSLError as ssl_error:
        print(f"SSL Error occurred: {ssl_error}")
        
        # Retry with SSL verification disabled (less secure)
        print("Retrying with SSL verification disabled...")
        kwargs['verify'] = False
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
        # Update existing transactions status (using razorpay_order_id field for Cashfree order IDs)
        expiry = timezone.now() - timedelta(hours=12)
        for transaction in Transaction.objects.filter(status__in=['created', 'ACTIVE'], timestamp__gte=expiry):
            try:
                if USE_MOCK_API:
                    mock_response = mock_cashfree_api(f'orders/{transaction.razorpay_order_id}', method='GET')
                    if mock_response['status_code'] == 200:
                        res = mock_response['json']
                        if res.get('order_status') != transaction.status:
                            transaction.status = res.get('order_status')
                            transaction.save()
                else:
                    # Skip API calls for now due to authentication issues
                    print(f"Skipping API call for transaction {transaction.id} due to auth issues")
                    continue
                        
            except Exception as e:
                print(f"Error checking transaction {transaction.id}: {e}")
                continue

        try:
            order_id = self.get_order_id(order_id)
            try:
                order_obj = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                return JsonResponse({'message': 'Invalid Order'})

            amount = float(order_obj.subscription_amount)
            unique_order_id = Transaction.generate_receipt()
            
            payload = {
                "order_amount": amount,
                "order_currency": "INR",
                "order_id": unique_order_id,
                "customer_details": {
                    "customer_id": str(request.user.id) if request.user.is_authenticated else "guest",
                    "customer_email": request.user.email if request.user.is_authenticated else "guest@lavaott.com",
                    "customer_phone": getattr(request.user, 'mobile_number', '9999999999') if request.user.is_authenticated else "9999999999"
                },
                "order_note": f"Subscription for Order #{order_obj.id}",
                "order_meta": {
                    "return_url": url_config['response_url']
                }
            }

            # Use correct Cashfree sandbox/production endpoint
            api_endpoint = 'https://sandbox.cashfree.com/pg/orders' if config.get('test_mode', True) else 'https://api.cashfree.com/pg/orders'
            
            if USE_MOCK_API:
                print("Using Mock Cashfree API")
                mock_response = mock_cashfree_api('orders', method='POST', json=payload)
                response_status = mock_response['status_code']
                res_dict = mock_response['json']
                print(f"Mock API Response: {res_dict}")
            else:
                print(f"Making real Cashfree API call to: {api_endpoint}")
                print(f"Payload: {payload}")
                print(f"Headers will include:")
                print(f"  x-client-id: {config['key_id']}")
                print(f"  x-client-secret: {config['key_secret'][:10]}...")
                
                response = make_cashfree_request(
                    api_endpoint,
                    method='POST',
                    json=payload
                )
                response_status = response.status_code
                print(f"Cashfree API response status: {response_status}")
                
                if response_status == 201:
                    res_dict = response.json()
                    print(f"Success! Response: {res_dict}")
                else:
                    print(f"Cashfree API request failed with status {response_status}")
                    print(f"Response text: {response.text}")
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', 'Payment gateway error')
                        print(f"Error data: {error_data}")
                    except:
                        error_msg = f'Payment gateway error (HTTP {response_status})'
                    
                    return render(request, 'error.html', {
                        'err_msg': error_msg
                    })

            # Check for Cashfree API errors in response
            if response_status != 201:
                msg = res_dict.get('message', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            # Create transaction record - Store Cashfree order ID in razorpay_order_id field
            transaction = Transaction.objects.create(
                razorpay_order_id=res_dict.get('order_id'),  # Store Cashfree order ID in existing field
                amount=amount,
                amount_due=res_dict.get('order_amount', amount),
                amount_paid=0,
                attempts=0,
                created_at=str(int(datetime.datetime.now().timestamp())),
                currency=res_dict.get('order_currency', 'INR'),
                entity='order',
                offer_id=None,
                receipt=unique_order_id,
                status=res_dict.get('order_status', 'ACTIVE'),
                order=order_obj,
                note_1=f"Subscription for Order #{order_obj.id}",
                note_2="Cashfree Payment"  # Indicator that this is a Cashfree transaction
            )
            
            print(f"Created transaction:")
            print(f"  Transaction ID: {transaction.id}")
            print(f"  Cashfree Order ID: {transaction.razorpay_order_id}")
            print(f"  Amount: {transaction.amount}")
            print(f"  Status: {transaction.status}")

            # Prepare data for checkout template
            checkout_data = {
                'key_id': config['key_id'],
                'environment': 'sandbox' if config.get('test_mode', True) else 'production',
                'order_id': transaction.razorpay_order_id,  # This now contains Cashfree order ID
                'payment_session_id': res_dict.get('payment_session_id'),
                'order_amount': amount,
                'order_currency': 'INR',
                'order_note': payload['order_note'],
                'customer_details': payload['customer_details'],
                'return_url': url_config['response_url']
            }

            return render(request, 'checkout.html', context={'data': checkout_data})
            
        except Exception as e:
            print(f"Checkout error: {e}")
            return JsonResponse({'message': str(e)})


class PaymentCheckoutTestView(PaymentCheckoutBaseView):
    """Test view using mock API"""
    def get(self, request, id):
        return self.handle_checkout(request, id)


class PaymentCheckoutView(PaymentCheckoutBaseView):
    """Live view"""
    def get(self, request, id):
        return self.handle_checkout(request, id)


class PaymentResponseView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        print(f"Cashfree payment response received: {response_data}")
        
        # Debug: Print all POST data
        for key, value in response_data.items():
            print(f"  {key}: {value}")

        # Handle Cashfree error responses
        if 'error' in response_data or response_data.get('order_status') == 'FAILED':
            error_description = response_data.get('error_description', 'Payment failed')
            order_id = response_data.get('order_id')
            
            try:
                if order_id:
                    # Using razorpay_order_id field to store Cashfree order ID
                    transaction = Transaction.objects.get(razorpay_order_id=order_id)
                    transaction.status = 'FAILED'
                    transaction.payment_timestamp = timezone.now()
                    transaction.payment_id = response_data.get('cf_payment_id', '')
                    transaction.save()
                    print(f"Updated transaction {transaction.id} status to FAILED")
            except Transaction.DoesNotExist:
                print(f"Transaction not found for order_id: {order_id}")
                pass
            
            return render(request, 'error.html', {'err_msg': error_description})

        try:
            order_id = response_data.get('order_id')
            print(f"Looking for transaction with order_id: {order_id}")
            
            if not order_id:
                print("No order_id found in response data")
                return JsonResponse({'message': 'No order ID provided'})
            
            # Using razorpay_order_id field to store Cashfree order ID
            try:
                transaction = Transaction.objects.get(razorpay_order_id=order_id)
                print(f"Found transaction: {transaction.id} with status: {transaction.status}")
            except Transaction.DoesNotExist:
                print(f"Transaction not found for order_id: {order_id}")
                # List all transactions for debug
                all_transactions = Transaction.objects.all().order_by('-id')[:5]
                print("Recent transactions:")
                for t in all_transactions:
                    print(f"  ID: {t.id}, Order ID: {t.razorpay_order_id}, Status: {t.status}")
                return JsonResponse({'message': f'Invalid order ID: {order_id}'})
            
            # Update transaction for successful payment
            if response_data.get('order_status') == 'PAID':
                transaction.status = 'PAID'
                transaction.payment_timestamp = timezone.now()
                transaction.payment_id = response_data.get('cf_payment_id', '')
                transaction.amount_paid = float(response_data.get('order_amount', transaction.amount))
                transaction.save()
                print(f"Updated transaction {transaction.id} status to PAID")

                # Update order
                order = transaction.order
                new_start_date = timezone.now()
                order.status = 'completed'
                order.is_active = True
                order.start_date = new_start_date
                order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
                order.save()
                print(f"Updated order {order.id} status to completed")

                return render(request, 'success.html')
            else:
                # Payment not successful
                transaction.status = response_data.get('order_status', 'FAILED')
                transaction.payment_timestamp = timezone.now()
                transaction.payment_id = response_data.get('cf_payment_id', '')
                transaction.save()
                print(f"Updated transaction {transaction.id} status to {transaction.status}")
                
                return render(request, 'error.html', {'err_msg': 'Payment was not successful'})
                
        except Exception as e:
            print(f"Payment response processing error: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'message': f'Error processing payment response: {str(e)}'})


class PaymentResponseTestView(APIView):
    def post(self, request):
        return JsonResponse({'response': request.POST.dict()})