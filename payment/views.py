# ===== UPDATED VIEWS.PY (Laravel Style) =====
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import render, redirect
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
        print(f"🟢 Using PRODUCTION API: {api_url}")
    else:
        api_url = 'https://sandbox.cashfree.com/pg/orders'
        print(f"🟡 Using SANDBOX API: {api_url}")
    
    return api_url, credentials_type

def make_cashfree_request(url, method='GET', **kwargs):
    """Make a secure request to Cashfree API with proper error handling"""
    headers = kwargs.get('headers', {})
    headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'x-client-id': config['key_id'],
        'x-client-secret': config['key_secret'],
        'x-api-version': '2022-01-01'  # Using same version as Laravel example
    })
    kwargs['headers'] = headers
    kwargs['timeout'] = kwargs.get('timeout', 30)
    kwargs['verify'] = True
    
    try:
        print(f"Making {method} request to: {url}")
        print(f"Using credentials: x-client-id={config['key_id']}")
        
        if method.upper() == 'POST':
            response = requests.post(url, **kwargs)
        else:
            response = requests.get(url, **kwargs)
            
        print(f"Response status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print(f"❌ API Error: {response.text}")
        
        return response
        
    except requests.exceptions.RequestException as e:
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
        print("\n" + "="*50)
        print("🚀 STARTING CHECKOUT PROCESS (Laravel Style)")
        print("="*50)
        
        # Get correct API endpoint based on credentials
        api_endpoint, credentials_type = get_correct_api_endpoint()
        
        try:
            order_id = self.get_order_id(order_id)
            try:
                order_obj = Order.objects.get(id=order_id)
                print(f"📋 Order found: #{order_obj.id}, Amount: ₹{order_obj.subscription_amount}")
            except Order.DoesNotExist:
                print("❌ Order not found")
                return JsonResponse({'message': 'Invalid Order'})

            amount = float(order_obj.subscription_amount)
            
            # Generate unique IDs (Laravel style)
            import random
            unique_order_id = f'order_{random.randint(1111111111, 9999999999)}'
            customer_id = f'customer_{random.randint(111111111, 999999999)}'
            
            print(f"🎫 Generated order ID: {unique_order_id}")
            print(f"👤 Generated customer ID: {customer_id}")
            
            # Customer details handling
            customer_phone = "9999999999"
            customer_name = "Guest User"
            customer_email = "guest@lavaott.com"
            
            if request.user.is_authenticated:
                customer_email = request.user.email or customer_email
                customer_name = getattr(request.user, 'first_name', 'Guest User') or "Guest User"
                
                if hasattr(request.user, 'mobile_number') and request.user.mobile_number:
                    customer_phone = str(request.user.mobile_number)
            
            print(f"👤 Customer: {customer_name} ({customer_email}) - {customer_phone}")
            
            # Build return URL with order_id and order_token placeholders (Laravel style)
            return_url = request.build_absolute_uri('/payment/response/') + '?order_id={order_id}&order_token={order_token}'
            print(f"🔗 Return URL: {return_url}")
            
            # Prepare payload (exactly like Laravel example)
            payload = {
                "order_id": unique_order_id,
                "order_amount": amount,
                "order_currency": "INR",
                "customer_details": {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "customer_email": customer_email,
                    "customer_phone": customer_phone,
                },
                "order_meta": {
                    "return_url": return_url
                }
            }
            
            print(f"🌐 Making Cashfree API call to: {api_endpoint}")
            print(f"📦 Payload: {json.dumps(payload, indent=2)}")
            
            response = make_cashfree_request(
                api_endpoint,
                method='POST',
                json=payload
            )
            
            if response.status_code in [200, 201]:
                res_dict = response.json()
                print(f"✅ SUCCESS! Cashfree response: {res_dict}")
                
                # Store payment details in database (like Laravel)
                transaction = Transaction.objects.create(
                    razorpay_order_id=unique_order_id,  # Store our order_id
                    amount=amount,
                    amount_due=amount,
                    amount_paid=0,
                    attempts=0,
                    created_at=str(int(datetime.datetime.now().timestamp())),
                    currency="INR",
                    entity='order',
                    offer_id=None,
                    receipt=unique_order_id,
                    status='created',  # Set as created initially
                    order=order_obj,
                    note_1=f"LavaOTT Subscription - Order #{order_obj.id}",
                    note_2=f"Cashfree Payment - {credentials_type.upper()}"
                )
                
                print(f"💾 Transaction created: ID={transaction.id}")
                
                # Check if we have payment_link (Laravel style)
                if 'payment_link' in res_dict:
                    print(f"🔗 Redirecting to payment_link: {res_dict['payment_link']}")
                    return redirect(res_dict['payment_link'])
                else:
                    # Fallback: render checkout page with session ID
                    checkout_data = {
                        'key_id': config['key_id'],
                        'environment': 'production' if credentials_type == 'production' else 'sandbox',
                        'order_id': unique_order_id,
                        'payment_session_id': res_dict.get('payment_session_id'),
                        'order_amount': amount,
                        'order_currency': 'INR',
                        'customer_details': payload['customer_details'],
                        'return_url': return_url.replace('{order_id}', unique_order_id).replace('{order_token}', res_dict.get('order_token', '')),
                        'cf_order_id': res_dict.get('cf_order_id'),
                        'order_token': res_dict.get('order_token'),
                    }
                    
                    print(f"🎨 Rendering checkout page...")
                    return render(request, 'checkout.html', context={'data': checkout_data})
            else:
                print(f"❌ API request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'Payment gateway error (HTTP {response.status_code})')
                except:
                    error_msg = f'Payment gateway error (HTTP {response.status_code})'
                
                return render(request, 'error.html', {'err_msg': error_msg})
                
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
    """Payment response handler (Laravel style)"""
    
    def get(self, request):
        """Handle GET response from Cashfree"""
        print(f"\n{'='*60}")
        print("🔔 CASHFREE RESPONSE RECEIVED (Laravel Style)")
        print(f"{'='*60}")
        
        # Get order_id from URL parameters
        order_id = request.GET.get('order_id')
        order_token = request.GET.get('order_token')
        
        print(f"Order ID: {order_id}")
        print(f"Order Token: {order_token}")
        print(f"All GET params: {request.GET.dict()}")
        
        if not order_id:
            print("❌ No order_id found in response")
            return render(request, 'error.html', {
                'err_msg': 'Payment verification failed: Missing order ID'
            })
        
        # Verify payment status with Cashfree API (like Laravel)
        try:
            api_endpoint, credentials_type = get_correct_api_endpoint()
            verify_url = f"{api_endpoint}/{order_id}"
            
            print(f"🔍 Verifying payment with Cashfree: {verify_url}")
            
            response = make_cashfree_request(verify_url, method='GET')
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"✅ Cashfree verification response: {response_data}")
                
                # Update payment status in database (like Laravel)
                try:
                    transaction = Transaction.objects.get(razorpay_order_id=order_id)
                    print(f"📋 Found transaction: {transaction.id}")
                    
                    # Check payment status
                    order_status = response_data.get('order_status', 'UNKNOWN')
                    is_paid = (order_status == 'PAID')
                    
                    transaction.status = 'paid' if is_paid else 'failed'
                    transaction.payment_timestamp = timezone.now()
                    transaction.payment_id = response_data.get('cf_order_id')
                    
                    if is_paid:
                        transaction.amount_paid = transaction.amount
                        
                        # Activate subscription (like Laravel success)
                        order = transaction.order
                        new_start_date = timezone.now()
                        order.status = 'completed'
                        order.is_active = True
                        order.start_date = new_start_date
                        order.expiration_date = get_expiry_date(new_start_date, period=order.subscription_period)
                        order.save()
                        print(f"🎉 Subscription activated for order {order.id}")
                    
                    transaction.save()
                    
                    if is_paid:
                        return render(request, 'success.html', {
                            'order_id': order_id,
                            'amount': transaction.amount,
                            'payment_id': transaction.payment_id,
                            'message': 'Payment Successful!'
                        })
                    else:
                        return render(request, 'error.html', {
                            'err_msg': f'Payment verification failed for Order ID: {order_id}'
                        })
                        
                except Transaction.DoesNotExist:
                    print(f"❌ Transaction not found for order_id: {order_id}")
                    return render(request, 'error.html', {
                        'err_msg': f'Invalid order ID: {order_id}'
                    })
            else:
                print(f"❌ Payment verification failed: {response.status_code} - {response.text}")
                return render(request, 'error.html', {
                    'err_msg': f'Payment verification failed: {response.text}'
                })
                
        except Exception as e:
            print(f"💥 Payment verification error: {e}")
            import traceback
            traceback.print_exc()
            return render(request, 'error.html', {
                'err_msg': f'Payment verification failed: {str(e)}'
            })
    
    def post(self, request):
        """Handle POST response from Cashfree (if any)"""
        return self.get(request)  # Use same logic

class PaymentResponseTestView(APIView):
    def post(self, request):
        return JsonResponse({'response': request.POST.dict()})
    
    def get(self, request):
        return JsonResponse({'response': request.GET.dict()})