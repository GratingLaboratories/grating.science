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
from . import utils

import os
import time
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
        existing = youtube_video_data_fetcher(v_id)
        if existing and existing.status != 'errored':
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
            if not existing:
                YouTubeVideos(v_id=v_id, status='succeeded', v_ext=v_ext, a_ext=a_ext).save()
            else:
                existing.status = 'succeeded'
                existing.save()
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
            cls.TPE.submit(cls._convert, y_video, params, pe)

    @classmethod
    def _convert(cls, y_video: YouTubeVideos, params, pe:ProcessEvent):
        wpl, ppl, width, height = params
        tmp_v_path = os.path.join(settings.TMP_DIR, '{}.{}'.format(pe.rid, 'mp4'))
        tmp_a_path = os.path.join(settings.TMP_DIR, '{}.{}'.format(pe.rid, 'mp3'))
        output_path = os.path.join(settings.VIDEO_OUTPUT_DIR, '{}.{}'.format(pe.rid, 'mp4'))
        v_input_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'video', '{}.{}'.format(y_video.v_id, y_video.v_ext))
        a_input_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'audio', '{}.{}'.format(y_video.v_id, y_video.a_ext))
        blk_a_path = os.path.join(settings.YOUTUBE_DOWNLOAD_DIR, 'audio', 'blank.mp3')

        logging.info(pe.status)
        if pe.status != 'queued':
            return

        while not os.path.exists(v_input_path) or not os.path.exists(a_input_path):
            time.sleep(3)

        cmd = 'python3 mvpcpy/cc.py -r {width} {height} -p {ppl:.2f} -w {wpl} {input} {output}'.format(
            width=width,
            height=height,
            ppl=ppl,
            wpl=wpl,
            input=v_input_path,
            output=tmp_v_path
        )

        pe.status = 'converting'
        pe.save()
        logging.info('Converting now')
        logging.info(cmd)
        subprocess.run(cmd.split())

        # Merge blank audio
        blank_cmd = "ffmpeg -i {b_p} -i {a_i} -filter_complex '[0:0][1:0]concat=n=2:v=0:a=1[out]' -map '[out]' {a_p}".format(
            b_p=blk_a_path,
            a_i=a_input_path,
            a_p=tmp_a_path
        )
        # subprocess.run(blank_cmd.split(), shell=True)
        os.system(blank_cmd)

        pe.status = 'compressing'
        pe.save()
        # Add audio
        mg_cmd = 'ffmpeg -i {t_p} -i {a_p} -vcodec libx264 -acodec copy {o_p}'.format(
            t_p=tmp_v_path,
            a_p=tmp_a_path,
            o_p=output_path
        )
        logging.info(mg_cmd)
        # subprocess.run(mg_cmd.split(), shell=True)
        os.system(mg_cmd)
        pe.status = 'succeeded'
        pe.save()

    @classmethod
    def append(cls, y_video: YouTubeVideos, params):
        wpl, ppl, width, height = params
        res = ProcessEvent.objects.filter(v_id=y_video, width=width, height=height, ppl=ppl, wpl=wpl)
        if len(res) == 0:
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
            pe.save()
            res = ProcessEvent.objects.filter(v_id=y_video, width=width, height=height, ppl=ppl, wpl=wpl)
            # cls._task_queue.put_nowait((y_video, params, pe))
        logging.info(len(res))
        cls._task_queue.put_nowait((res[0].v_id, params, res[0]))


@require_http_methods(['POST', ])
def youtube_link(request):
    v_id = request.POST.get('v_id')
    agreed = request.POST.get('no_cc', None)

    if not v_id:
        return JsonResponse(dict(info='Vid Error', code=1))

    if v_id == '0000':
        YouTubeVideos.objects.get_or_create(v_id=v_id, status='succeeded', v_ext='mp4', a_ext='mp3')
        return JsonResponse(dict(code=0), status=202)

    try:
        with youtube_dl.YoutubeDL() as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=' + v_id, download=False)
            # if not agreed and not info.get('license').endswith('(reuse allowed)'):
            #     return JsonResponse(dict(info='License Error', code=2))
    except:
        return JsonResponse(dict(info='Video Not Found', code=4))

    YouTubeDownloader.append(v_id)
    return JsonResponse(dict(code=0), status=202)


@require_http_methods(['POST', ])
def convert(request):
    try:
        wpl = int(request.POST.get('wpl'))
        ppl = float(request.POST.get('ppl'))
        width = int(request.POST.get('width'))
        height = int(request.POST.get('height'))
        v_id = request.POST.get('v_id')
    except (ValueError, TypeError):
        return JsonResponse(dict(info='Invalid Parameters', code=8))

    if not all([wpl, ppl, width, height, v_id]):
        return JsonResponse(dict(code=16, info='Insufficient Parameters'))

    y_video = youtube_video_data_fetcher(v_id)
    if not y_video:
        return JsonResponse(dict(code=32, info='Video Not Found'))

    VideoConverter.append(y_video, (wpl, ppl, width, height))
    return JsonResponse(dict(code=0), status=202)


@require_http_methods(['GET', ])
def fetch_calibration(request):
    try:
        width = int(request.GET.get('width'))
        height = int(request.GET.get('height'))
        cali_stage = request.GET.get('stage')
        if cali_stage.lower() == 'ppl':
            ppl = int(request.GET.get('ppl'))
        else:
            ppl = float(request.GET.get('ppl'))
    except (ValueError, TypeError):
        return HttpResponse(status=404)

    filename = '{}_{}@{}'.format(width, height, ppl)
    response = HttpResponse()

    if not 0 < ppl < 30 or width <= 0 or height <= 0:
        return HttpResponse(status=404)

    if cali_stage.lower() == 'ppl':
        filename += '_ppl.png'
        if not os.path.exists(os.path.join(settings.CALIB_PIC_DIR, filename)):
            utils.mk_ppl_img(os.path.join(settings.CALIB_PIC_DIR, filename), width, height, ppl)
    elif cali_stage.lower() == 'wpl':
        filename += '_wpl.png'
        if not os.path.exists(os.path.join(settings.CALIB_PIC_DIR, filename)):
            utils.mk_wpl_img(os.path.join(settings.CALIB_PIC_DIR, filename), width, height, ppl)
    else:
        return HttpResponse(status=404)

    response['Content-Type'] = 'image/png'
    response['X-Accel-Redirect'] = os.path.join('/cali/', filename)
    return response


@require_http_methods(['GET', ])
def query_status(request):
    try:
        wpl = int(request.GET.get('wpl'))
        ppl = float(request.GET.get('ppl'))
        width = int(request.GET.get('width'))
        height = int(request.GET.get('height'))
        v_id = request.GET.get('v_id')
    except (ValueError, TypeError):
        return JsonResponse(dict(code=64, info='Invalid Parameters'))

    if not all([wpl, ppl, width, height, v_id]):
        return JsonResponse(dict(code=128, info='Insufficient Parameters'))

    q_res = ProcessEvent.objects.filter(v_id=youtube_video_data_fetcher(v_id), width=width, height=height, ppl=ppl, wpl=wpl)
    if len(q_res) == 0:
        return JsonResponse(dict(code=256, info='Task Not Found'))
    else:
        res = q_res[0]
        if res.status == 'succeeded':
            return JsonResponse(dict(code=0, status=res.status, link='/output/{}.{}'.format(res.rid, res.v_ext)))
        else:
            return JsonResponse(dict(code=0, status=res.status))


@require_http_methods(['GET', ])
def index(request):
    return render(request, 'mvpcpy/index.html')


@require_http_methods(['GET', ])
def test(request):
    return HttpResponse(None)


ydt = Thread(target=YouTubeDownloader.start, name='YouTubeDownloader', daemon=True).start()
cvt = Thread(target=VideoConverter.start, name='VideoConverter', daemon=True).start()
