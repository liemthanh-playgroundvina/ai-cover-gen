import json

from celery import Task
from ai_celery.celery_app import app
from configs.env import settings
from ai_celery.common import Celery_RedisClient, CommonCeleryService

from main import song_cover_pipeline


class AICoverGenTask(Task):
    """
    Abstraction of Celery's Task class to support AI Cover GEN
    """
    abstract = True

    def __init__(self):
        super().__init__()

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


@app.task(
    bind=True,
    base=AICoverGenTask,
    name="{query}.{task_name}".format(
        query=settings.AI_QUERY_NAME,
        task_name=settings.AI_COVER_GEN
    ),
    queue=settings.AI_COVER_GEN
)
def ai_cover_gen_task(self, task_id: str, data: bytes, task_request: bytes, file: bytes):
    """
    Service AI Cover Gen tasks

    task_request example:
        {
            "youtube_link": "https://www.youtube.com/watch?v=2lSiBrLvNW4",
            "artist_name": "Naruto"
        }
    """
    print("============= AI Cover Gen task: Started ===================")
    try:
        # Load data
        data = json.loads(data)
        request = json.loads(task_request)
        file = json.loads(file)
        Celery_RedisClient.started(task_id, data)

        # Request
        youtube_link = request.get('youtube_link')
        artist_name = request.get('artist_name')
        pitch_voice = request.get('pitch_voice', 0)
        pitch_all = request.get('pitch_all', 0)

        # Predict
        if youtube_link != "":
            url_file = ai_cover_gen(youtube_link, artist_name, pitch_voice, pitch_all)
        else:
            audio_file = file.get('filename').split("/")[-1]
            audio_file = "/app/static/public/ai_cover_gen/" + audio_file
            url_file = ai_cover_gen(audio_file, artist_name, pitch_voice, pitch_all)

        # Successful
        metadata = {
            "task": "ai_cover_gen",
            "tool": "local",
            "model": "rvc_v2",
            "usage": None,
        }
        response = {"url_file": url_file, "metadata": metadata}
        Celery_RedisClient.success(task_id, data, response)
        return

    except Exception as e:
        print(str(e))
        err = {'code': "500", 'message': "Internal Server Error"}
        Celery_RedisClient.failed(task_id, data, err)
        return


def ai_cover_gen(audio_file: str, artist_name: str, pitch_change_voice: int, pitch_change_all: int):
    instrumentals_path, ai_vocals_path, ai_cover_path = song_cover_pipeline(
        audio_file,
        artist_name,
        pitch_change=pitch_change_voice,
        pitch_change_all=pitch_change_all,
        keep_files=True
    )
    # Save s3
    url_instrumentals = CommonCeleryService.upload_s3_file(
        instrumentals_path,
        "audio/wav",
        settings.AI_COVER_GEN
    )
    ai_vocals_url = CommonCeleryService.upload_s3_file(
        ai_vocals_path,
        "audio/wav",
        settings.AI_COVER_GEN
    )
    ai_cover_url = CommonCeleryService.upload_s3_file(
        ai_cover_path,
        "audio/mpeg",
        settings.AI_COVER_GEN
    )
    return {
        "instrumental": url_instrumentals,
        "ai_vocal": ai_vocals_url,
        "ai_cover": ai_cover_url
    }
