import os

YOUTUBE_DOWNLOAD_DIR = '/data/grating.science/data/youtube-dl/'
TMP_DIR = '/data/grating.science/data/tmp/'
VIDEO_OUTPUT_DIR = '/data/grating.science/data/output/'
CALIB_PIC_DIR = '/data/grating.science/data/cali'


for key, path in locals().copy().items():
    if key.endswith('_DIR'):
        if not os.path.exists(path):
            os.makedirs(path)


OUTPUT_FILENAME_LEN = 20

ydl_audio_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': os.path.join(YOUTUBE_DOWNLOAD_DIR, 'audio', '%(id)s.%(ext)s')
}

ydl_video_opts = {
    'format': 'bestvideo/mp4',
    'outtmpl': os.path.join(YOUTUBE_DOWNLOAD_DIR, 'video', '%(id)s.%(ext)s')
}