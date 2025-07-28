from django.db import models
from django.contrib.auth.models import AbstractUser
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .utils import str_to_json


class User(AbstractUser):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('T', 'Transgender'), ('O', 'Others')]

    mobile_number = models.CharField(max_length=25, unique=True)

    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    dob = models.DateField(blank=True, null=True)

    is_subscriber = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    image = models.ImageField(upload_to='user_image/', blank=True, null=True)

    def has_subscription(self):
        from videos.utils import subscription_exists
        return subscription_exists(self)

    def get_active_subscription(self):
        from videos.utils import get_order
        from videos.models import Order
        from django.core.exceptions import MultipleObjectsReturned
        try:
            order = Order.objects.get(user=self, status='completed', is_active=True, expiration_date__gt=timezone.now())
            order = get_order(order)
        except Order.DoesNotExist:
            order = {}
        except Order.MultipleObjectsReturned:
            raise MultipleObjectsReturned

        return order


class CustomSession(models.Model):
    session_key = models.CharField(max_length=200, db_index=True, primary_key=True)
    session_data = models.TextField()
    expire_date = models.DateTimeField()
    inactive_count = models.IntegerField()

    @classmethod
    def generate_session_key(cls):
        key = Fernet.generate_key()
        if cls.objects.filter(session_key=key.decode()).exists():
            cls.generate_session_key()
        return key

    @classmethod
    def set_session(cls, user, session_type='web', keep_me_logged_in=None):
        key = cls.generate_session_key()
        f = Fernet(key)

        if session_type == 'web':
            data = {'user_id': user.id}
        else:
            data = {'mobile_number': user.mobile_number, 'user_id': user.id}

        session_data = f.encrypt(str(data).encode()).decode()
        key = key.decode()

        expiry_sec = cls.get_expiry(keep_me_logged_in)
        expiry = timezone.now() + timedelta(seconds=expiry_sec)

        cls(session_key=key, session_data=session_data, expire_date=expiry, inactive_count=expiry_sec).save()
        return key

    @classmethod
    def get_session(cls, token):
        try:
            obj = cls.objects.get(session_key=token)

            if obj.session_expired():
                return False

            session_data = obj.session_data.encode()
            f = Fernet(token.encode())
            data = f.decrypt(session_data).decode()
            data = str_to_json(data)
            print('Data: ', data)

            user = User.objects.get(id=data['user_id'])

            obj.expire_date = timezone.now() + timedelta(seconds=obj.inactive_count)
            obj.save()

            print('Current Exp date: ', obj.expire_date)

            return user
        except User.DoesNotExist:
            print('No user exists. or invalid token...')
        except Exception as e:
            print('Error: ', str(e))
        return False

    @classmethod
    def delete_session(cls, token):
        try:
            cls.objects.get(session_key=token).delete()
        except:
            pass

    @classmethod
    def delete_expired_sessions(cls):
        today = timezone.now() - timedelta(days=1)
        cls.objects.filter(expire_date__lte=today).delete()

    @classmethod
    def get_expiry(cls, keep_me_logged_in=None):
        if keep_me_logged_in is True:
            expiry = settings.USER_KEEP_SESSION_AGE
        elif keep_me_logged_in is False:
            expiry = settings.USER_SESSION_AGE
        else:
            expiry = settings.ADMIN_SESSION_AGE
        print('session_age: ', expiry)
        return expiry

    def session_expired(self):
        expire_date = self.expire_date
        current_time = timezone.now()
        print(expire_date, current_time)
        if expire_date < current_time:
            return True


class Project(models.Model):
    field1 = models.BooleanField(default=False)
    field2 = models.BooleanField(default=False)


class DeletedUser(models.Model):
    mobile_number = models.CharField(max_length=50)
    reason = models.CharField(max_length=200)
    remarks = models.CharField(max_length=200, blank=True, null=True)
