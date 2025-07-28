from django.shortcuts import render


def error_404_view(req, excep):
    return render(req, '404.html', status=200)


def error_403_view(req, reason=''):
    return render(req, '404.html', status=200)
