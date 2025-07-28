from .models import Order
from django.utils import timezone


def get_expiry_date(date, period):
    from datetime import timedelta
    # if period == 'month':
    #     days = 31
    # elif period == 'year':
    #     days = 365.25
    # else:
    #     days = 0

    exp_date = date + timedelta(int(period))
    print('Calculated Expiry date = ', date, '+', period, '=', exp_date)
    return exp_date


def get_order(order):
    start_date = order.start_date.astimezone() if order.start_date else ''
    expiration_date = order.expiration_date.astimezone() if order.expiration_date else ''
    return {
        "id": order.id,
        "user": order.user.get_full_name(),
        "subscription_amount": order.subscription_amount,
        "subscription_period": order.subscription_period,
        "status": order.status,
        "created_at": order.created_at.strftime("%d %m %Y"),
        "start_date": start_date.strftime("%d/%m/%Y") if order.start_date else '',
        "start_time": start_date.strftime("%H:%M%p") if order.start_date else '',
        "expiration_date": expiration_date.strftime("%d/%m/%Y") if order.expiration_date else '',
        "expiration_time": expiration_date.strftime("%H:%M%p") if order.expiration_date else '',
        "is_active": order.is_active,
    }


def get_orders(user):
    orders1 = Order.objects.filter(user=user, status='completed').order_by('-start_date')
    orders2 = Order.objects.filter(user=user).exclude(status='completed').order_by('-created_at')
    # orders = orders1.union(orders2).order_by('-start_date')
    orders = [get_order(order) for order in orders1] + [get_order(order) for order in orders2]

    return orders


def subscription_exists(user):
    from .models import Order

    orders = Order.objects.filter(user=user, status='completed')
    now_date = timezone.now()
    current_orders = orders.filter(start_date__lte=now_date, expiration_date__gt=now_date, is_active=True)
    later_orders = orders.filter(start_date__gte=now_date, expiration_date__gt=now_date, is_active=True)

    curr_order = None
    if current_orders.exists():
        curr_order = current_orders.earliest('start_date')

    elif later_orders.exists():
        curr_order = later_orders.earliest('start_date')

    if curr_order:
        curr_order.is_active = True
        curr_order.save()
        orders.exclude(id=curr_order.id).update(is_active=False)
        return True

    if orders.exists():
        orders.update(is_active=False)
    return False


def get_video(video, app=None):
    # if app is True:
    #     file = video.file.url if video.file else ''
        # trailer = 'https://s3.ap-south-1.amazonaws.com/4handstudio.in/videos/web+1920x1080.mp4'
        # file = 'https://s3.ap-south-1.amazonaws.com/4handstudio.in/videos/lava+test+1min.mp4'
    # else:
    #     file = ''
    return {
        "id": video.id,
        "name": video.name,
        "description": video.description,
        "thumbnail": video.thumbnail.url if video.thumbnail else '',
        "trailer": video.trailer.url if video.trailer else '',
        "file": video.file.url if video.file else '',
        "director": video.director,
        "duration": get_hours(video.duration) if video.duration else '',
        "cast": video.cast,
        "watch_count": video.watch_count,
        "watch_hours": get_hours(video.watch_hours) if video.watch_hours else ''
    }


def rounded(val):
    w = str(val)
    if '.' in w:
        w = w.split('.')
        w = w[0] + '.' + w[1][:2]
    return w


def get_hours(sec):
    sec = float(sec)
    mint = sec / 60
    hr = mint / 60
    print(sec, mint, hr)
    if hr >= 1:
        output = f'{rounded(hr)} hours'
    elif mint >= 1:
        output = f'{rounded(mint)} minutes'
    else:
        output = f'{rounded(sec)} seconds'
    return output
