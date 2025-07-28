from rest_framework import serializers
from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class OTPSendSerializer(serializers.Serializer):
    mobile_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    otp_data = serializers.BooleanField(default=False)
    keep_me_logged_in = serializers.BooleanField(default=True)


class OTPVerfySerializer(serializers.Serializer):
    mobile_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999,
                                   error_messages={'max_value': 'OTP must contain 6 digits.',
                                                   'min_value': 'OTP must contain 6 digits.'})
    keep_me_logged_in = serializers.BooleanField(default=True)
    otp_data = serializers.BooleanField(default=False)


class RegistrationOTPVerfySerializer(serializers.Serializer):
    mobile_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999,
                                   error_messages={'max_value': 'OTP must contain 6 digits.',
                                                   'min_value': 'OTP must contain 6 digits.'})


class UserDeleteOTPVerfySerializer(serializers.Serializer):
    mobile_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000, max_value=999999,
                                   error_messages={'max_value': 'OTP must contain 6 digits.',
                                                   'min_value': 'OTP must contain 6 digits.'})
    reason = serializers.CharField(max_length=200)


class UserRegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    mobile_number = serializers.IntegerField(min_value=1000000000, max_value=9999999999)

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'mobile_number',
            'gender',
            'dob',
        )

    def create(self, validated_data):
        validated_data.update({'username': validated_data.get('mobile_number')})
        return User.objects.create(**validated_data)


class ProfileImageSerializer(serializers.Serializer):
    image = serializers.ImageField()
