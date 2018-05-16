from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from functools import lru_cache
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from urllib import parse
from threading import Thread

from .models import YouTubeVideos, ProcessEvent
from . import settings

import os
import random
import logging
import subprocess
import youtube_dl


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
        logging.info('YouTube downloader daemon is running now')
        while not cls.stop:
            v_id = cls._task_queue.get()
            logging.info('Start downloading ' + v_id)
            cls.TPE.submit(cls._download, v_id)

    @classmethod
    def _download(cls, v_id: str):
        if youtube_video_data_fetcher(v_id):
            return

        try:
            y_url = 'https://www.youtube.com/watch?v=' + v_id

            logging.info('Download from ' + y_url)
            with youtube_dl.YoutubeDL(settings.ydl_audio_opts) as ydl:
                ydl.download([y_url, ])

            with youtube_dl.YoutubeDL(settings.ydl_video_opts) as ydl:
                ydl.download([y_url, ])

            origin_v_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'video')
            origin_a_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'audio')
            v_ext = list(filter(lambda x: x.startswith(v_id), os.listdir(origin_v_path)))[0].split('.')[-1]
            a_ext = list(filter(lambda x: x.startswith(v_id), os.listdir(origin_a_path)))[0].split('.')[-1]

            YouTubeVideos(v_id=v_id, status='succeeded', v_ext=v_ext, a_ext=a_ext).save()
        except Exception as exc:
            YouTubeVideos(v_id=v_id, status='errored').save()

    @classmethod
    def append(cls, v_id):
        cls._task_queue.put_nowait(v_id)


class VideoConverter:
    stop = False
    _concurrency = 5
    _task_queue = Queue()

    @classmethod
    def start(cls):
        cls.TPE = ThreadPoolExecutor(max_workers=cls._concurrency)
        logging.info('Video converter daemon is running now')
        while not cls.stop:
            y_video, params, pe = cls._task_queue.get()
            logging.info('Converting')
            print(cls.TPE.submit(cls._convert, y_video, params, pe).result())

    @classmethod
    def _convert(cls, y_video: YouTubeVideos, params, pe:ProcessEvent):
        print('In _convert')
        wpl, ppl, width, height = params
        tmp_path = os.path.join(settings.TMP_DIR, y_video.v_id)
        output_path = os.path.join(settings.VIDEO_OUTPUT_DIR, '{}.{}'.format(pe.rid, 'mp4'))
        v_input_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'video', '{}.{}'.format(y_video.v_id, y_video.v_ext))
        a_input_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'audio', '{}.{}'.format(y_video.v_id, y_video.a_ext))
        os.makedirs(tmp_path, exist_ok=True)
        cmd = 'python3 mvpcpy/cc.py -r {width} {height} -p {ppl:.2f} -w {wpl} {input} {output}'.format(
            width=width,
            height=height,
            ppl=ppl,
            wpl=wpl,
            input=v_input_path,
            output=output_path
        )

        pe.status = 'running'
        pe.save()
        logging.info('Converting now')
        logging.info(cmd)
        subprocess.run(cmd.split())
        pe.status = 'succeeded'

    @classmethod
    def append(cls, y_video: YouTubeVideos, params):
        wpl, ppl, width, height = params
        print(ProcessEvent.objects.filter(v_id=y_video, width=width, height=height, ppl=ppl, wpl=wpl))
        if len(ProcessEvent.objects.filter(v_id=y_video, width=width, height=height, ppl=ppl, wpl=wpl)) == 0:
            pe = ProcessEvent(
                v_id=y_video,
                width=width,
                height=height,
                ppl=ppl,
                wpl=wpl,
                status='queued',
                v_ext=y_video.v_ext,
                rid='{:02X}'.format(random.getrandbits(settings.OUTPUT_FILENAME_LEN * 4))
            )
            cls._task_queue.put_nowait((y_video, params, pe))
            pe.save()


@require_http_methods(['POST', ])
@csrf_exempt
def youtube_link(request):
    v_id = request.POST.get('v_id')

    if not v_id:
        return JsonResponse(dict(result=False, info='Vid Error'))

    try:
        with youtube_dl.YoutubeDL() as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=' + v_id, download=False)
            # if not info.get('license').endswith('(reuse allowed)'):
            #     return JsonResponse(dict(result=False, info='License Error'))
    except:
        return JsonResponse(dict(result=False, info='Video Not Found'))

    YouTubeDownloader.append(v_id)
    return JsonResponse(dict(result=True), status=202)


@require_http_methods(['POST', ])
@csrf_exempt
def convert(request):
    try:
        wpl = int(request.POST.get('wpl'))
        ppl = float(request.POST.get('ppl'))
        width = int(request.POST.get('width'))
        height = int(request.POST.get('height'))
        v_id = request.POST.get('v_id')
    except ValueError:
        return JsonResponse(dict(result=False, info='Invalid Parameters'))

    if not all([wpl, ppl, width, height, v_id]):
        return JsonResponse(dict(result=False, info='Insufficient Parameters'))

    y_video = youtube_video_data_fetcher(v_id)
    if not y_video:
        return JsonResponse(dict(result=False, info='Video Not Found'))

    VideoConverter.append(y_video, (wpl, ppl, width, height))
    return JsonResponse(dict(result=True), status=202)


@require_http_methods(['GET', ])
def query_status(request):
    return JsonResponse(dict(result=True))


@require_http_methods(['GET', ])
@csrf_exempt
def test(request):
    return HttpResponse(None)


ydt = Thread(target=YouTubeDownloader.start, name='YouTubeDownloader', daemon=True).start()
cvt = Thread(target=VideoConverter.start, name='VideoConverter', daemon=True).start()
