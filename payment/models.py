from django.db import models


TRAN_STATUS = [
    ('created', 'created'),
    ('attempted', 'attempted'),
    ('paid', 'paid'),
    ('failed', 'failed'),
]


class Transaction(models.Model):
    razorpay_order_id = models.CharField(max_length=200, unique=True)
    amount = models.FloatField()
    amount_due = models.FloatField()
    amount_paid = models.FloatField()
    attempts = models.IntegerField(default=0)
    created_at = models.CharField(max_length=30)
    currency = models.CharField(max_length=10)
    entity = models.CharField(max_length=30)
    offer_id = models.CharField(max_length=50, blank=True, null=True)
    receipt = models.CharField(max_length=50)

    note_1 = models.CharField(max_length=250)
    note_2 = models.CharField(max_length=250)

    status = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    payment_timestamp = models.DateTimeField(null=True)
    payment_id = models.CharField(max_length=50, blank=True, null=True)

    order = models.ForeignKey('videos.Order', on_delete=models.SET_NULL, null=True)

    @classmethod
    def generate_receipt(cls):
        from random import randint
        from django.db.models import Max
        d = Transaction.objects.aggregate(latest_id=Max('id', default=1))
        return f'receipt{int(d.get("latest_id")) + 1}_{randint(10000, 99999)}{randint(10000, 99999)}'

