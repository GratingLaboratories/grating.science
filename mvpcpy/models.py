from django.db import models
from .settings import OUTPUT_FILENAME_LEN


class YouTubeVideos(models.Model):
    v_id = models.CharField(max_length=16, primary_key=True)
    v_ext = models.CharField(max_length=8, null=True)
    a_ext = models.CharField(max_length=8, null=True)
    status = models.TextField()
    download_date = models.DateTimeField(auto_now=True)


class ProcessEvent(models.Model):
    v_id = models.ForeignKey(YouTubeVideos, on_delete=models.CASCADE)
    width = models.IntegerField()
    height = models.IntegerField()
    ppl = models.DecimalField(max_digits=4, decimal_places=2)
    wpl = models.IntegerField()
    status = models.TextField()
    v_ext = models.CharField(max_length=8, default='mp4')
    rid = models.CharField(max_length=OUTPUT_FILENAME_LEN)
