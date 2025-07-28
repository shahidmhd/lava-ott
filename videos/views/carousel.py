from rest_framework.decorators import api_view
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from ..serializers import CarouselSerializer, CarouselListSerializer
from ..forms import CarouselForm
from ..models import Carousel
from users.utils import add_success_response, add_error_response, format_errors
from rest_framework.decorators import authentication_classes, permission_classes


@api_view(['POST'])
def carousel_create(request):
    serializer = CarouselSerializer(data=request.data)
    if serializer.is_valid():
        images = serializer.validated_data.get('image')
        print('images = ', images)

        carousel_objs = [Carousel(image=image) for image in images]

        Carousel.objects.all().delete()
        Carousel.objects.bulk_create(carousel_objs)

        data = {'message': 'Carousel created successfully.'}
        return add_success_response(data, status=status.HTTP_201_CREATED)

    else:
        data = {'error': format_errors(serializer.errors)}
        return add_error_response(data, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def carousel_list(request):
    carousel = Carousel.objects.all()
    data = {'data': [c.image.url for c in carousel]}
    return add_success_response(data, status=status.HTTP_200_OK)

