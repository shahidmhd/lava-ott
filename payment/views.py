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

from .models import Transaction
from videos.models import Order
from django.conf import settings
from videos.utils import get_expiry_date

url_config = settings.PAYMENT_URL_CONFIG
config = settings.PAYMENT_CONFIG

def detect_credentials_type():
    """Automatically detect if credentials are production or sandbox"""
    key_secret = config.get('key_secret', '')
    if key_secret.startswith('cfsk_ma_prod_'):
        return 'production'
    elif key_secret.startswith('cfsk_ma_test_'):
        return 'sandbox'
    else:
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

def make_cashfree_request(url, method='GET', **kwargs):
    """Make a secure request to Cashfree API with proper error handling"""
    session = requests.Session()
    
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

class PaymentCheckoutTestView(APIView):
    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def get(self, request, **kwargs):
        from json import loads
        config = self.get_key_config()
        
        # Get correct API endpoint
        api_endpoint, credentials_type = get_correct_api_endpoint()
        
        # Update existing transactions status (exactly like Razorpay)
        expiry = timezone.now() - timedelta(hours=12)
        for i in Transaction.objects.filter(status='created', timestamp__gte=expiry):
            try:
                # Verify with Cashfree API
                verify_url = f"{api_endpoint}/{i.razorpay_order_id}"
                headers = {
                    'Accept': 'application/json',
                    'x-client-id': config['key_id'],
                    'x-client-secret': config['key_secret'],
                    'x-api-version': '2023-08-01'
                }
                
                res = requests.get(verify_url, headers=headers)
                if res.status_code == 200:
                    res_data = res.json()
                    cashfree_status = res_data.get('order_status', 'ACTIVE')
                    # Map Cashfree status to Razorpay-like status
                    mapped_status = 'created' if cashfree_status == 'ACTIVE' else cashfree_status.lower()
                    
                    if mapped_status != i.status:
                        i.status = mapped_status
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

            # Same transaction checks as Razorpay (commented out like in original)
            exp_time = timezone.now() - timedelta(minutes=10)
            trans = Transaction.objects.filter(order=order_obj, timestamp__gte=exp_time)
            # if trans.exists():
            #     return render(request, 'error.html', {'err_msg': 'Payment already Initiated. Try after 10 minutes.'})

            trans = Transaction.objects.filter(order=order_obj, status='attempted')
            # if trans.exists():
            #     return render(request, 'error.html', {'err_msg': 'Payment under processing. Try again later.'})

            amount = int(order_obj.subscription_amount)

            # Cashfree payload - minimal like Razorpay
            payload = {
                "order_amount": amount,  # Cashfree uses direct amount (not *100)
                "order_currency": "INR",
                "order_id": Transaction.generate_receipt(),  # Use receipt as order_id
                "customer_details": {
                    "customer_id": "guest_user",
                    "customer_email": "guest@lavaott.com",
                    "customer_phone": "9999999999",
                    "customer_name": "Guest User"
                },
                "order_meta": {
                    "return_url": url_config['response_url']  # Use production URL
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            
            response = make_cashfree_request(
                api_endpoint,
                method='POST',
                json=payload
            )

            print('------------- Checkout Response ------------')
            print('status code : ', response.status_code)
            print('response : ', response.text)
            print('------------- Checkout Response End ------------')
            
            res_dict = loads(response.text)

            # Error Response (exactly like Razorpay)
            if 'error' in res_dict:
                msg = res_dict.get('message', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            order_id = res_dict.get('order_id')  # Cashfree order_id

            # Save to Transaction Table (EXACTLY like Razorpay)
            transaction = Transaction()
            transaction.razorpay_order_id = res_dict.get('order_id')
            transaction.amount = amount
            transaction.amount_due = res_dict.get('order_amount', amount)
            transaction.amount_paid = 0  # Always 0 initially
            transaction.attempts = 0  # Always 0 initially
            transaction.created_at = str(int(datetime.datetime.now().timestamp()))  # Same format as Razorpay
            transaction.currency = res_dict.get('order_currency', 'INR')
            transaction.entity = 'order'
            transaction.offer_id = None
            transaction.receipt = payload['order_id']  # Our generated receipt
            transaction.status = 'created'  # Always 'created' initially like Razorpay
            transaction.order = order_obj
            transaction.save()
            
            config = self.get_key_config()
            
            # Return data EXACTLY like Razorpay (no customer details in template data)
            res_dict = {
                'key_id': config['key_id'],
                'response_url': url_config['response_url'],
                'id': order_id,  # Cashfree order ID
                # Additional Cashfree specific data for checkout
                'payment_session_id': res_dict.get('payment_session_id'),
                'order_amount': amount,
                'environment': 'production' if credentials_type == 'production' else 'sandbox'
            }
            print(res_dict)

            return render(request, 'checkout.html', context={'data': res_dict})
            
        except Exception as e:
            return JsonResponse({'message': str(e)})


class PaymentCheckoutView(PaymentCheckoutTestView):
    def get_key_config(self):
        return config

    def get_order_id(self, order_id):
        from base64 import b64decode
        return b64decode(order_id).decode()[6:]

    def get(self, request, **kwargs):
        from json import loads
        config = self.get_key_config()
        
        # Get correct API endpoint
        api_endpoint, credentials_type = get_correct_api_endpoint()
        
        # Update existing transactions status (exactly like Razorpay)
        expiry = timezone.now() - timedelta(hours=12)
        for i in Transaction.objects.filter(status='created', timestamp__gte=expiry):
            try:
                verify_url = f"{api_endpoint}/{i.razorpay_order_id}"
                headers = {
                    'Accept': 'application/json',
                    'x-client-id': config['key_id'],
                    'x-client-secret': config['key_secret'],
                    'x-api-version': '2023-08-01'
                }
                
                res = requests.get(verify_url, headers=headers)
                if res.status_code == 200:
                    res_data = res.json()
                    cashfree_status = res_data.get('order_status', 'ACTIVE')
                    mapped_status = 'created' if cashfree_status == 'ACTIVE' else cashfree_status.lower()
                    
                    if mapped_status != i.status:
                        i.status = mapped_status
                        i.save()
            except Exception as e:
                continue

        try:
            order_id = kwargs.get('id')
            order_id = self.get_order_id(order_id)

            try:
                order_obj = Order.objects.get(id=order_id)
            except:
                return JsonResponse({'message': 'Invalid Order'})

            # Same restrictions as Razorpay (ENABLED in live version)
            exp_time = timezone.now() - timedelta(minutes=10)
            trans = Transaction.objects.filter(order=order_obj, status='created', timestamp__gte=exp_time)
            if trans.exists():
                return render(request, 'error.html', {'err_msg': 'Payment already Initiated. Try after 10 minutes.'})

            trans = Transaction.objects.filter(order=order_obj, status='attempted')
            if trans.exists():
                return render(request, 'error.html', {'err_msg': 'Payment under processing. Try again later.'})

            amount = int(order_obj.subscription_amount)

            # Cashfree payload
            payload = {
                "order_amount": amount,
                "order_currency": "INR",
                "order_id": Transaction.generate_receipt(),
                "customer_details": {
                    "customer_id": "guest_user",
                    "customer_email": "guest@lavaott.com",
                    "customer_phone": "9999999999",
                    "customer_name": "Guest User"
                },
                "order_meta": {
                    "return_url": url_config['response_url']
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            
            response = make_cashfree_request(
                api_endpoint,
                method='POST',
                json=payload
            )

            print('------------- Checkout Response ------------')
            print('status code : ', response.status_code)
            print('response : ', response.text)
            print('------------- Checkout Response End ------------')
            
            res_dict = loads(response.text)

            # Error Response
            if 'error' in res_dict:
                msg = res_dict.get('message', 'Payment gateway error')
                return render(request, 'error.html', {'err_msg': msg})

            # Save to Transaction Table
            transaction = Transaction()
            transaction.razorpay_order_id = res_dict.get('order_id')
            transaction.amount = amount
            transaction.amount_due = res_dict.get('order_amount', amount)
            transaction.amount_paid = 0
            transaction.attempts = 0
            transaction.created_at = str(int(datetime.datetime.now().timestamp()))
            transaction.currency = res_dict.get('order_currency', 'INR')
            transaction.entity = 'order'
            transaction.offer_id = None
            transaction.receipt = payload['order_id']
            transaction.status = 'created'
            transaction.order = order_obj
            transaction.save()

            # Return data exactly like Razorpay
            res_dict.update({
                'key_id': config['key_id'],
                'response_url': url_config['response_url'],
                'order_amount': amount,
                'environment': 'production' if credentials_type == 'production' else 'sandbox'
            })

            return render(request, 'checkout.html', context={'data': res_dict})
            
        except Exception as e:
            return JsonResponse({'message': str(e)})


class PaymentResponseView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        print(f"Cashfree payment response received (POST): {response_data}")
        return self._process_response(request, response_data)
    
    def get(self, request):
        response_data = request.GET.dict()
        print(f"Cashfree payment response received (GET): {response_data}")
        
        # If no payment data, return debug info
        if not response_data:
            print("⚠️ No payment data received - returning debug response")
            recent_transactions = Transaction.objects.all().order_by('-id')[:3]
            return JsonResponse({
                'message': 'No payment response data received',
                'recent_transactions': [
                    {
                        'id': t.id,
                        'order_id': t.razorpay_order_id,
                        'status': t.status,
                        'created': t.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    } for t in recent_transactions
                ],
                'instructions': 'Complete a payment to see response data here'
            })
        
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
                    transaction.payment_timestamp = datetime.datetime.now()
                    transaction.payment_id = response_data.get('cf_payment_id', '')
                    transaction.save()
                    print(f"Updated transaction {transaction.id} status to failed")
                except Transaction.DoesNotExist:
                    print(f"Transaction not found for failed order_id: {order_id}")
            
            return render(request, 'error.html', {'err_msg': error_description})

        # Handle successful payment
        order_id = response_data.get('order_id')
        if not order_id:
            print("❌ No order_id found in response")
            return JsonResponse({'message': 'No order ID provided'})
        
        try:
            transaction = Transaction.objects.get(razorpay_order_id=order_id)
            
            # Check payment status - FIXED: Cashfree sends 'PAID' not 'paid'
            order_status = response_data.get('order_status', '').upper()
            print(f"📊 Payment status from Cashfree: {order_status}")
            
            if order_status == 'PAID':  # ✅ FIXED: Check for 'PAID' (uppercase)
                # Payment successful
                from django.utils import timezone
                from videos.utils import get_expiry_date
                
                cf_payment_id = response_data.get('cf_payment_id', '')
                
                transaction.status = 'paid'  # Store as lowercase in database
                transaction.payment_timestamp = datetime.datetime.now()
                transaction.payment_id = cf_payment_id
                transaction.amount_paid = float(response_data.get('order_amount', transaction.amount))
                transaction.save()
                
                print(f"✅ Transaction {transaction.id} marked as PAID")

                # Activate subscription (exactly like Razorpay)
                new_start_date = timezone.now()
                order = transaction.order
                order.status = 'completed'
                order.is_active = True
                order.start_date = new_start_date
                order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
                order.save()
                
                print(f"🎉 Subscription activated for order {order.id}")

                return render(request, 'success.html')
            else:
                # Payment not successful
                cf_payment_id = response_data.get('cf_payment_id', '')
                
                transaction.status = 'failed'
                transaction.payment_timestamp = datetime.datetime.now()
                transaction.payment_id = cf_payment_id
                transaction.save()
                print(f"⚠️ Payment failed with status: {order_status}")
                
                return render(request, 'error.html', {
                    'err_msg': f'Payment was not successful. Status: {order_status}'
                })
                
        except Transaction.DoesNotExist:
            print(f"❌ Transaction not found for order_id: {order_id}")
            return JsonResponse({'message': 'Invalid order ID'})
        except Exception as e:
            print(f"💥 Error processing payment: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'message': f'Error processing payment: {str(e)}'})
            
        # Fallback return (should never reach here, but just in case)
        return JsonResponse({'message': 'Payment processing completed'})


class PaymentResponseTestView(APIView):
    def post(self, request):
        response_data = request.POST.dict()
        return JsonResponse({'response': response_data})
    
    def get(self, request):
        response_data = request.GET.dict()
        return JsonResponse({'response': response_data})