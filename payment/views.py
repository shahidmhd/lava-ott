import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
import json
import urllib3

from .models import Transaction
from videos.models import Order
from django.conf import settings
from videos.utils import get_expiry_date

url_config = settings.PAYMENT_URL_CONFIG
config = settings.PAYMENT_CONFIG

USE_MOCK_API = False

def detect_credentials_type():
    """Automatically detect if credentials are production or sandbox"""
    key_secret = config.get('key_secret', '')
    if key_secret.startswith('cfsk_ma_prod_'):
        return 'production'
    elif key_secret.startswith('cfsk_ma_test_'):
        return 'sandbox'
    else:
        # Fallback to test_mode setting
        return 'sandbox' if config.get('test_mode', True) else 'production'

def get_correct_api_endpoint():
    """Get the correct API endpoint based on credential type"""
    credentials_type = detect_credentials_type()
    
    if credentials_type == 'production':
        api_url = 'https://api.cashfree.com/pg/orders'
        print(f"🟢 Using PRODUCTION API: {api_url} (detected production credentials)")
    else:
        api_url = 'https://sandbox.cashfree.com/pg/orders'
        print(f"🟡 Using SANDBOX API: {api_url} (detected sandbox credentials)")
    
    return api_url, credentials_type

def mock_cashfree_api(endpoint, method='GET', **kwargs):
    """Mock Cashfree API responses for testing"""
    if method == 'POST' and 'orders' in endpoint:
        payload = kwargs.get('json', {})
        mock_order_id = payload.get('order_id', f'order_prod_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}')
        return {
            'status_code': 201,
            'json': {
                'cf_order_id': 12345,
                'created_at': datetime.datetime.now().isoformat(),
                'customer_details': payload.get('customer_details', {}),
                'entity': 'order',
                'order_amount': payload.get('order_amount', 100.0),
                'order_currency': payload.get('order_currency', 'INR'),
                'order_expiry_time': (datetime.datetime.now() + timedelta(minutes=15)).isoformat(),
                'order_id': mock_order_id,
                'order_meta': {'return_url': url_config['response_url']},
                'order_note': payload.get('order_note', ''),
                'order_status': 'ACTIVE',
                'order_tags': None,
                'payment_session_id': f'session_prod_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'
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
    
    headers = kwargs.get('headers', {})
    headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'x-client-id': config['key_id'],
        'x-client-secret': config['key_secret'],
        'x-api-version': '2023-08-01'
    })
    kwargs['headers'] = headers
    kwargs['timeout'] = kwargs.get('timeout', 30)
    kwargs['verify'] = True
    
    try:
        print(f"Making {method} request to: {url}")
        print(f"Using credentials: x-client-id={config['key_id']}")
        print(f"Credential type: {detect_credentials_type().upper()}")
        
        if method.upper() == 'POST':
            response = session.post(url, **kwargs)
        else:
            response = session.get(url, **kwargs)
            
        print(f"Response status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print(f"❌ API Error: {response.text}")
        
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed with error: {e}")
        raise

def verify_payment_with_cashfree(order_id):
    """Verify payment status with Cashfree API"""
    if USE_MOCK_API:
        mock_response = mock_cashfree_api(f'orders/{order_id}', method='GET')
        return mock_response['status_code'] == 200, mock_response['json']
    
    try:
        api_endpoint, _ = get_correct_api_endpoint()
        verify_url = f"{api_endpoint}/{order_id}"
        
        response = make_cashfree_request(verify_url, method='GET')
        
        if response.status_code == 200:
            return True, response.json()
        else:
            print(f"Payment verification failed: {response.status_code} - {response.text}")
            return False, {}
            
    except Exception as e:
        print(f"Error verifying payment: {e}")
        return False, {}

class PaymentCheckoutBaseView(APIView):
    """Shared base for test and live checkout views"""

    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def handle_checkout(self, request, order_id):
        print("\n" + "="*50)
        print("🚀 STARTING CHECKOUT PROCESS")
        print("="*50)
        
        # Get correct API endpoint based on credentials
        api_endpoint, credentials_type = get_correct_api_endpoint()
        
        # Update existing transactions status
        expiry = timezone.now() - timedelta(hours=12)
        for transaction in Transaction.objects.filter(status__in=['created', 'ACTIVE'], timestamp__gte=expiry):
            try:
                success, payment_data = verify_payment_with_cashfree(transaction.razorpay_order_id)
                if success and payment_data.get('order_status') != transaction.status:
                    transaction.status = payment_data.get('order_status', transaction.status)
                    transaction.save()
                        
            except Exception as e:
                print(f"Error checking transaction {transaction.id}: {e}")
                continue

        try:
            order_id = self.get_order_id(order_id)
            try:
                order_obj = Order.objects.get(id=order_id)
                print(f"📋 Order found: #{order_obj.id}, Amount: ₹{order_obj.subscription_amount}")
            except Order.DoesNotExist:
                print("❌ Order not found")
                return JsonResponse({'message': 'Invalid Order'})

            amount = float(order_obj.subscription_amount)
            unique_order_id = Transaction.generate_receipt()
            print(f"🎫 Generated order ID: {unique_order_id}")
            
            # Customer details handling
            customer_phone = "9999999999"
            customer_name = "Guest User"
            customer_email = "guest@lavaott.com" 
            customer_id = "guest_user"
            
            if request.user.is_authenticated:
                customer_id = str(request.user.id)
                customer_email = request.user.email or customer_email
                customer_name = getattr(request.user, 'first_name', 'Guest User') or "Guest User"
                
                if hasattr(request.user, 'mobile_number') and request.user.mobile_number:
                    customer_phone = str(request.user.mobile_number)
            
            print(f"👤 Customer: {customer_name} ({customer_email}) - {customer_phone}")
            
            payload = {
                "order_amount": amount,
                "order_currency": "INR",
                "order_id": unique_order_id,
                "customer_details": {
                    "customer_id": customer_id,
                    "customer_email": customer_email,
                    "customer_phone": customer_phone,
                    "customer_name": customer_name
                },
                "order_note": f"LavaOTT Subscription - Order #{order_obj.id}",
                "order_meta": {
                    "return_url": url_config['response_url'],
                    "notify_url": url_config.get('webhook_url', url_config['response_url'])
                }
            }
            
            if USE_MOCK_API:
                print("🧪 Using Mock Cashfree API")
                mock_response = mock_cashfree_api('orders', method='POST', json=payload)
                response_status = mock_response['status_code']
                res_dict = mock_response['json']
                print(f"Mock API Response: {res_dict}")
            else:
                print(f"🌐 Making Cashfree API call to: {api_endpoint}")
                print(f"📦 Payload: {json.dumps(payload, indent=2)}")
                
                response = make_cashfree_request(
                    api_endpoint,
                    method='POST',
                    json=payload
                )
                response_status = response.status_code
                print(f"📡 API Response Status: {response_status}")
                
                if response_status in [200, 201]:
                    res_dict = response.json()
                    print(f"✅ SUCCESS! Order created: {res_dict.get('order_id')}")
                    print(f"🔑 Payment Session ID: {res_dict.get('payment_session_id')}")
                else:
                    print(f"❌ API request failed with status {response_status}")
                    print(f"Response: {response.text}")
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', f'Payment gateway error (HTTP {response_status})')
                        print(f"Error details: {error_data}")
                    except:
                        error_msg = f'Payment gateway error (HTTP {response_status})'
                    
                    return render(request, 'error.html', {
                        'err_msg': error_msg
                    })

            if response_status not in [200, 201]:
                msg = res_dict.get('message', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            # Create transaction record
            transaction = Transaction.objects.create(
                razorpay_order_id=res_dict.get('order_id'),
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
                note_1=f"LavaOTT Subscription - Order #{order_obj.id}",
                note_2=f"Cashfree Payment - {credentials_type.upper()}"
            )
            
            print(f"💾 Transaction created: ID={transaction.id}")

            # Checkout data
            checkout_data = {
                'key_id': config['key_id'],
                'environment': 'production' if credentials_type == 'production' else 'sandbox',
                'order_id': transaction.razorpay_order_id,
                'payment_session_id': res_dict.get('payment_session_id'),
                'order_amount': amount,
                'order_currency': 'INR',
                'order_note': payload['order_note'],
                'customer_details': payload['customer_details'],
                'return_url': url_config['response_url'],
                'cf_order_id': res_dict.get('cf_order_id'),
                'order_token': res_dict.get('order_token'),
            }

            print(f"🎨 Rendering checkout page...")
            print("="*50 + "\n")
            return render(request, 'checkout.html', context={'data': checkout_data})
            
        except Exception as e:
            print(f"💥 Checkout error: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'message': str(e)})

class PaymentCheckoutTestView(PaymentCheckoutBaseView):
    """Test view"""
    def get(self, request, id):
        return self.handle_checkout(request, id)

class PaymentCheckoutView(PaymentCheckoutBaseView):
    """Live view"""
    def get(self, request, id):
        return self.handle_checkout(request, id)

class PaymentResponseView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        print(f"\n🔔 Cashfree payment response received (POST): {response_data}")
        return self._process_response(request, response_data)
    
    def get(self, request):
        response_data = request.GET.dict()
        print(f"\n🔔 Cashfree payment response received (GET): {response_data}")
        return self._process_response(request, response_data)
    
    def _process_response(self, request, response_data):
        """Process payment response from Cashfree"""
        
        print("\n" + "="*50)
        print("💳 PROCESSING PAYMENT RESPONSE")
        print("="*50)
        
        for key, value in response_data.items():
            print(f"  {key}: {value}")

        # Handle error responses
        if 'error' in response_data or response_data.get('order_status') == 'FAILED':
            error_description = response_data.get('error_description', 'Payment failed')
            order_id = response_data.get('order_id')
            
            print(f"❌ Payment failed for order {order_id}: {error_description}")
            
            if order_id:
                try:
                    transaction = Transaction.objects.get(razorpay_order_id=order_id)
                    transaction.status = 'failed'
                    transaction.payment_timestamp = timezone.now()
                    transaction.payment_id = response_data.get('cf_payment_id', '')
                    transaction.save()
                    print(f"Updated transaction {transaction.id} status to FAILED")
                except Transaction.DoesNotExist:
                    print(f"Transaction not found for failed order_id: {order_id}")
            
            return render(request, 'error.html', {'err_msg': error_description})

        try:
            order_id = response_data.get('order_id')
            print(f"🔍 Processing order_id: {order_id}")
            
            if not order_id:
                print("❌ No order_id found in response")
                return JsonResponse({'message': 'No order ID provided'})
            
            try:
                transaction = Transaction.objects.get(razorpay_order_id=order_id)
                print(f"📋 Found transaction: {transaction.id} (status: {transaction.status})")
            except Transaction.DoesNotExist:
                print(f"❌ Transaction not found for order_id: {order_id}")
                return JsonResponse({'message': f'Invalid order ID: {order_id}'})
            
            # Verify payment with Cashfree API
            success, payment_verification = verify_payment_with_cashfree(order_id)
            
            if success:
                api_status = payment_verification.get('order_status', 'UNKNOWN')
                print(f"✅ API verification successful: {api_status}")
            else:
                api_status = response_data.get('order_status', 'UNKNOWN')
                print(f"⚠️ API verification failed, using response status: {api_status}")
            
            # Process successful payment
            if api_status == 'PAID' or (not success and response_data.get('order_status') == 'PAID'):
                transaction.status = 'paid'
                transaction.payment_timestamp = timezone.now()
                transaction.payment_id = response_data.get('cf_payment_id', payment_verification.get('cf_payment_id', ''))
                transaction.amount_paid = float(response_data.get('order_amount', transaction.amount))
                transaction.save()
                print(f"✅ Transaction {transaction.id} marked as PAID")

                # Activate subscription
                order = transaction.order
                new_start_date = timezone.now()
                order.status = 'completed'
                order.is_active = True
                order.start_date = new_start_date
                order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
                order.save()
                print(f"🎉 Subscription activated for order {order.id}")

                return render(request, 'success.html', {
                    'order_id': order_id,
                    'amount': transaction.amount,
                    'payment_id': transaction.payment_id
                })
            else:
                # Payment not successful
                transaction.status = 'failed'
                transaction.payment_timestamp = timezone.now()
                transaction.payment_id = response_data.get('cf_payment_id', '')
                transaction.save()
                print(f"⚠️ Payment not successful: {api_status}")
                
                return render(request, 'error.html', {
                    'err_msg': f'Payment was not successful. Status: {api_status}'
                })
                
        except Exception as e:
            print(f"💥 Payment response processing error: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'message': f'Error processing payment response: {str(e)}'})

class PaymentResponseTestView(APIView):
    def post(self, request):
        return JsonResponse({'response': request.POST.dict()})
    
    def get(self, request):
        return JsonResponse({'response': request.GET.dict()})