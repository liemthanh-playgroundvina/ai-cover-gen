import logging
import json
import shutil
import requests
from urllib.parse import urlparse, unquote
import os

from celery import Task
from ai_celery.celery_app import app
from configs.env import settings
from ai_celery.common import Celery_RedisClient, CommonCeleryService
from celery.exceptions import SoftTimeLimitExceeded
from amqp.exceptions import PreconditionFailed

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
    time_limit=300,
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
    print(f"============= AI Cover Gen task {task_id}: Started ===================")
    try:
        # Load data
        data = json.loads(data)
        request = json.loads(task_request)
        file = json.loads(file)
        Celery_RedisClient.started(task_id, data)

        # Check task removed
        Celery_RedisClient.check_task_removed(task_id)

        # Request
        youtube_link = request.get('youtube_link')
        artist_name = request.get('artist_name')
        pitch_voice = request.get('pitch_voice', 0)
        pitch_all = request.get('pitch_all', 0)

        # Check artist name
        check_artist_name(artist_name)

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

    except ValueError as e:
        logging.getLogger().error(str(e), exc_info=True)
        err = {'code': "400", 'message': str(e)}
        Celery_RedisClient.failed(task_id, data, err)
        return
    except SoftTimeLimitExceeded:
        e = "Task was terminated after exceeding the time limit."
        logging.getLogger().error(str(e), exc_info=True)
        err = {'code': "500", 'message': "Internal Server Error"}
        Celery_RedisClient.failed(task_id, data, err)
        return
    except PreconditionFailed:
        e = "Time out to connect into broker."
        logging.getLogger().error(str(e), exc_info=True)
        err = {'code': "500", 'message': "Internal Server Error"}
        Celery_RedisClient.failed(task_id, data, err)
        return
    except Exception as e:
        logging.getLogger().error(str(e), exc_info=True)
        err = {'code': "500", 'message': "Internal Server Error"}
        Celery_RedisClient.failed(task_id, data, err)
        return


def check_artist_name(artist_name):
    with open('../rvc_models/models.json', 'r') as file:
        models = json.load(file)
    # Find model in json
    voice_model = None
    for model in models:
        if model['name'] == artist_name:
            voice_model = model
            break

    # Find dir model
    voice_dir_model = None
    dir_models = os.listdir("../rvc_models")
    for dir in dir_models:
        if dir == artist_name:
            voice_dir_model = dir
            break

    if voice_model is not None and voice_dir_model is not None:
        return
    elif voice_model is not None and voice_dir_model is None:
        # Download model to dir /rvc_models
        voice_path = f"../rvc_models/{voice_model['name']}"
        if os.path.exists(voice_path):
            shutil.rmtree(voice_path)
        os.makedirs(voice_path)
        write_file_from_s3(voice_model['url']['model'], voice_path)
        write_file_from_s3(voice_model['url']['index'], voice_path)
    else:
        raise ValueError(f"Could not find artist_name '{artist_name}' model")


def write_file_from_s3(url, destination_path: str = "../rvc_models/default_voice"):
    response = requests.get(url)

    parsed_url = urlparse(url)
    filename = unquote(parsed_url.path.split('/')[-1])
    file_path = os.path.join(destination_path, filename)
    if response.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(response.content)
        print("Download completed successfully.")
    else:
        raise Exception(f"Can't download file '{url}' from s3")


def ai_cover_gen(audio_file: str, artist_name: str, pitch_change_voice: int, pitch_change_all: int):
    instrumentals_path, ai_vocals_path, ai_cover_path = song_cover_pipeline(
        audio_file,
        artist_name,
        pitch_change=pitch_change_voice,
        pitch_change_all=pitch_change_all,
        keep_files=True,
        output_format='wav',
    )
    print(ai_vocals_path)
    # Save s3
    ai_vocals_url = CommonCeleryService.upload_s3_file(
        ai_vocals_path,
        "audio/wav",
        settings.AI_COVER_GEN
    )
    print(instrumentals_path)
    url_instrumentals = CommonCeleryService.upload_s3_file(
        instrumentals_path,
        "audio/wav",
        settings.AI_COVER_GEN
    )
    print(ai_cover_path)
    ai_cover_url = CommonCeleryService.upload_s3_file(
        ai_cover_path,
        "audio/wav",
        settings.AI_COVER_GEN
    )
    print("Done")
    return {
        "instrumental": url_instrumentals,
        "ai_vocal": ai_vocals_url,
        "ai_cover": ai_cover_url
    }
