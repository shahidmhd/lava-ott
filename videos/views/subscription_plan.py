from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..serializers import SubscriptionPlanSerializer
from ..models import SubscriptionPlan
from users.utils import add_success_response, add_error_response
from rest_framework.decorators import authentication_classes, permission_classes


@api_view(['POST'])
def subscription_plan_create(request):
    print('------------ Inside Subsc Plan create ---------------')
    serializer = SubscriptionPlanSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()

        data = {'message': 'Subscription plan created'}
        return add_success_response(data, status=status.HTTP_201_CREATED)
    else:
        return add_error_response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def subscription_plan_list(request):
    sub_plans = SubscriptionPlan.objects.all()
    serializer = SubscriptionPlanSerializer(sub_plans, many=True)
    return add_success_response({'data': serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
def subscription_plan_app_list(request):
    data = [
        {
            "id": 1,
            "subscription_amount": 224.00,
            "subscription_period": 30
        },
        {
            "id": 2,
            "subscription_amount": 355.0,
            "subscription_period": 90
        },
        {
            "id": 3,
            "subscription_amount": 888.0,
            "subscription_period": 365
        }
    ]
    return add_success_response({'data': data}, status=status.HTTP_200_OK)


@api_view(['POST'])
def subscription_plan_delete(request):
    sub_plan_id = request.data.get('id')
    try:
        sub_plan = SubscriptionPlan.objects.get(pk=sub_plan_id)
        sub_plan.delete()
        return add_success_response({'message': 'Subscription plan deleted.'}, status=status.HTTP_200_OK)
    except SubscriptionPlan.DoesNotExist:
        return add_error_response({'error': 'ID does not exist.'}, status=status.HTTP_200_OK)
