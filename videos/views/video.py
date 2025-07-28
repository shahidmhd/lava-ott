from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..serializers import VideoCreateSerializer, VideoListSerializer
from ..models import Video
from users.utils import add_success_response, add_error_response, format_errors, get_paginated_list


class VideoCreateView(APIView):
    def post(self, request):
        user = request.customuser
        print('Logged In User --- ', user)
        video_id = request.data.get('id')
        if video_id:
            video = get_object_or_404(Video, id=video_id)
            serializer = VideoCreateSerializer(video, data=request.data)
            msg = 'Video updated successfully'
        else:
            serializer = VideoCreateSerializer(data=request.data)
            msg = 'Video created successfully'

        if serializer.is_valid():
            obj = serializer.save(view_on_app=True, created_by=user)
            print('Saved !!!!!')

            # Set duration
            # Moviepy
            # from moviepy.video.io.VideoFileClip import VideoFileClip
            from django.conf import settings
            import os
            # Opencv
            # import cv2
            # file_path = settings.MEDIA_ROOT + '/', obj.file.name
            # print('file path = ', file_path)
            # clip = VideoFileClip(file_path)
            # d = clip.duration
            # print('duration  = ', d)
            # clip.close()

            # cv = cv2.VideoCapture(file_path)
            # fps = cv.get(cv2.CAP_PROP_FPS)
            # seconds = cv.get(cv2.CAP_PROP_FRAME_COUNT)
            #
            # print('----------- opencv response -----------')
            # print('fps -- ', fps)
            # print('sec -- ', seconds)
            # duration = seconds / fps
            # print('duration -- ', duration)

            # obj.duration = duration
            obj.save()

            return add_success_response({
                'message': msg
            }, status=status.HTTP_201_CREATED)
        else:
            return add_error_response({
                'error': format_errors(serializer.errors)
            })


class VideoListView(APIView):

    def get(self, request):
        from ..utils import get_video
        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 9)

        video_id = request.GET.get('id')
        if not video_id:
            videos = Video.objects.all()
            data = get_paginated_list(videos, page, per_page)
            # serializer = VideoListSerializer(data['data'], many=True)
            data['data'] = [get_video(i) for i in data['data']]
            # print('data ---- ', data)
            return add_success_response(data)
        else:
            video = get_object_or_404(Video, id=video_id)
            # serializer = VideoListSerializer(video)
            return add_success_response({'data': get_video(video)})


class VideoDeleteView(APIView):
    def post(self, request):
        video_id = request.data.get('id')
        try:
            video = Video.objects.get(id=video_id)
            video.delete()
        except Video.DoesNotExist:
            return add_error_response({'message': 'ID does not exist.'})
        return add_success_response({'message': 'Video deleted.'})
