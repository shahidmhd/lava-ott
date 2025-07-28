from rest_framework import serializers
from .models import Carousel, SubscriptionPlan, Video, Order


class CarouselSerializer(serializers.Serializer):
    image = serializers.ListField(child=serializers.ImageField(), max_length=8)

    def validate_image(self, value):
        for image in value:
            print(image.size)
            if image.size > 1 * 1024 * 1024:
                raise serializers.ValidationError("File size should not exceed 1MB.")

            if image.name.split('.')[-1].strip() not in ('jpg', 'JPG', 'jpeg', 'JPEG'):
                raise serializers.ValidationError("File format should be jpg or jpeg.")
        return value


class CarouselListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carousel
        fields = ['image']


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            'id',
            'subscription_amount',
            'subscription_period'
        )


class VideoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = (
            'name',
            'description',
            'thumbnail',
            'trailer',
            'file',
            'director',
            'cast',
            'created_by'
        )

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024 * 1024  # 5MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError("Video size should not exceed 5GB.")
        if value.name.split('.')[-1].strip() not in ('mp4', 'MP4'):
            raise serializers.ValidationError("Video format should be mp4.")
        return value

    def validate_trailer(self, value):
        max_size = 1 * 1024 * 1024 * 1024  # 1GB in bytes
        if value.size > max_size:
            raise serializers.ValidationError("Trailer size should not exceed 1GB.")
        if value.name.split('.')[-1].strip() not in ('mp4', 'MP4'):
            raise serializers.ValidationError("Trailer format should be mp4.")
        return value

    # Validate file size for the thumbnail (1MB)
    def validate_thumbnail(self, value):
        max_size = 1 * 1024 * 1024  # 1MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError("Thumbnail size should not exceed 1MB.")
        if value.name.split('.')[-1].strip() not in ('jpg', 'JPG', 'jpeg', 'JPEG'):
            raise serializers.ValidationError("Thumbnail format should be jpg or jpeg.")
        return value


class VideoListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = (
            'id',
            'name',
            'description',
            'thumbnail',
            # 'trailer',
            # 'file',
            'director',
            'cast',
            'watch_count',
            'view_on_app',
            'watch_hours',
            'duration',
            # 'delete_flag',
            # 'created_at',
            # 'created_by'
        )


class OrderCreateSerializer(serializers.ModelSerializer):
    # subscription_period = serializers.ChoiceField(choices=[('year', 'year'), ('month', 'month')])

    class Meta:
        model = Order
        fields = (
            'subscription_amount',
            'subscription_period',
        )


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            'id',
            'subscription_amount',
            'subscription_period',
            'status',
            'created_at',
            'start_date',
            'expiration_date',
            'is_active'
        )



