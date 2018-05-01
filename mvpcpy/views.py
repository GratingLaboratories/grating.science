from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from functools import lru_cache
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from urllib import parse

from .models import YouTubeVideos, ProcessEvent
from . import settings

import os
import subprocess
import youtube_dl



@lru_cache(maxsize=128)
def youtube_video_data_fetcher(v_id: str):
    q_res = YouTubeVideos.objects.filter(v_id=v_id)
    if q_res:
        return q_res[0]
    else:
        return None


class YouTubeDownloader:
    stop = False
    _concurrency = 3
    _task_queue = Queue()

    @classmethod
    def start(cls):
        cls.TPE = ThreadPoolExecutor(max_workers=cls._concurrency)
        while not cls.stop:
            v_id = cls._task_queue.get()
            cls.TPE.submit(cls._download, v_id)

    @classmethod
    def _download(cls, v_id: str):
        if youtube_video_data_fetcher(v_id):
            return

        try:
            y_url = 'https://www.youtube.com/watch?v=' + v_id
            with youtube_dl.YoutubeDL(settings.ydl_audio_opts) as ydl:
                ydl.download([y_url, ])

            with youtube_dl.YoutubeDL(settings.ydl_video_opts) as ydl:
                ydl.download([y_url, ])

            YouTubeVideos(v_id=v_id, status='succeeded').save()

        except Exception as exc:
            YouTubeVideos(v_id=v_id, status='errored').save()

    @classmethod
    def append(cls, v_id):
        cls._task_queue.put_nowait(v_id)


@require_http_methods(['POST', ])
def youtube_link(request):
    v_id = request.POST.get('v_id')

    if not v_id:
        return JsonResponse(dict(result=False, info='Vid Error'))

    try:
        with youtube_dl.YoutubeDL() as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=' + v_id, download=False)
            if not info.get('license').endswith('(reuse allowed)'):
                return JsonResponse(dict(result=False, info='License Error'))
    except:
        return JsonResponse(dict(result=False, info='Video Not Found'))

    YouTubeDownloader.append(v_id)
    return JsonResponse(dict(result=True), status=202)


@require_http_methods(['POST', ])
def convert(request):
    return HttpResponse(status=202)


@require_http_methods(['GET', ])
def query_status(request):
    return JsonResponse(dict(result=True))


@require_http_methods(['GET', ])
@csrf_exempt
def test(request):
    return HttpResponse(None)


