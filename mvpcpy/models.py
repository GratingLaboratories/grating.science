from django.db import models
from .settings import OUTPUT_FILENAME_LEN


class YouTubeVideos(models.Model):
    v_id = models.CharField(max_length=16, primary_key=True)
    download_date = models.DateTimeField(auto_now=True)
    status = models.TextField()


class ProcessEvent(models):
    v_id = models.ForeignKey(YouTubeVideos, on_delete=models.CASCADE)
    width = models.IntegerField()
    height = models.IntegerField()
    ppl = models.DecimalField(max_digits=4, decimal_places=2)
    wpl = models.IntegerField()
    rid = models.CharField(max_length=OUTPUT_FILENAME_LEN + 10) # Reserved for filename extension
    status = models.TextField()
