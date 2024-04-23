import logging
import json
import shutil
import requests
from urllib.parse import urlparse, unquote
import os

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from typing import Optional, Text
from pydantic import BaseModel, validator

from main import preprocess_song
from main import mdxnet_models_dir, urlparse, get_youtube_video_id, get_hash, raise_exception, get_audio_paths

logging.config.fileConfig("logging.ini",
                          disable_existing_loggers=False)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("BASE_DIR: ", BASE_DIR)


@app.get("/model/{voice_id}")
async def get_model_pretrained(voice_id: str):
    """
    Get model information from voice_id at ~/rvc_model/
    """
    try:
        with open('../rvc_models/models.json', 'r') as file:
            models = json.load(file)
        # Find model following voice_id
        voice_model = None
        for model in models:
            if model['name'] == voice_id:
                voice_model = model

        return {
            "status_code": 200,
            "message": "",
            "data": voice_model
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.getLogger('app').error(str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class ModelData(BaseModel):
    voice_id: str
    s3_model_url: str
    s3_index_url: str

@app.post("/model")
async def insert_model_pretrained(request: ModelData):
    """
    Insert model from voice_id into ~/rvc_model/{voice_id}
    """
    try:
        with open('../rvc_models/models.json', 'r') as file:
            models = json.load(file)
        models = [item for sublist in models for item in (sublist if isinstance(sublist, list) else [sublist])]
        # Insert model following voice_id
        new_model = {"name": request.voice_id, "path": request.voice_id, "url": {"model": request.s3_model_url, "index": request.s3_index_url}}
        print(models)
        print(new_model)
        models.append(new_model)
        print(models)
        # Download model to dir /rvc_models
        voice_path = f"../rvc_models/{request.voice_id}"
        if os.path.exists(voice_path):
            shutil.rmtree(voice_path)
        os.makedirs(voice_path)
        write_file_from_s3(request.s3_model_url, voice_path)
        write_file_from_s3(request.s3_index_url, voice_path)

        # Write the updated list back to the file
        with open('../rvc_models/models.json', 'w') as file:
            json.dump(models, file, indent=4)

        return {
            "status_code": 200,
            "message": "Successfully",
            "data": new_model
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.getLogger('app').error(str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/separate-audio")
async def separate_audio(files: list, youtube_link: list):
    """
    Process audio (youtube_link to audio file & separate voice in audio file)

    Note: Volume mapped: /static/public/ai_cover_gen
    """
    try:
        # youtube_link to audio
        audios = []
        for link in youtube_link:

            audio_separated = process_audio(link)
            audios.append(audio_separated)
        for file in files:
            file = "../" + file
            audios.append(process_audio(file))

        free_gpu()
        return {
            "status_code": 200,
            "message": "",
            "data": audios
        }

    except ValueError as e:
        free_gpu()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        free_gpu()
        logging.getLogger('app').error(str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def process_audio(song_input: str) -> Text:
    output_dir = os.path.join(BASE_DIR, 'song_output')
    is_webui = 0
    keep_files = True
    with open(os.path.join(mdxnet_models_dir, 'model_data.json')) as infile:
        mdx_model_params = json.load(infile)

    # if youtube url
    if urlparse(song_input).scheme == 'https':
        input_type = 'yt'
        song_id = get_youtube_video_id(song_input)
        if song_id is None:
            raise ValueError(f"Youtube link '{song_input}' don't existed")

    # local audio file
    else:
        input_type = 'local'
        song_input = song_input.strip('\"')
        if os.path.exists(song_input):
            song_id = get_hash(song_input)
        else:
            error_msg = f'{song_input} does not exist.'
            song_id = None
            raise_exception(error_msg, is_webui)

    song_dir = os.path.join(output_dir, song_id)

    if not os.path.exists(song_dir):
        os.makedirs(song_dir)
        _, vocals_path, _, _, _, _ = preprocess_song(
            song_input, mdx_model_params, song_id, is_webui, input_type, None)
    else:
        vocals_path, main_vocals_path = None, None
        paths = get_audio_paths(song_dir)

        # if any of the audio files aren't available or keep intermediate files, rerun preprocess
        if any(path is None for path in paths) or keep_files:
            orig_song_path, vocals_path, instrumentals_path, main_vocals_path, backup_vocals_path, main_vocals_dereverb_path = preprocess_song(
                song_input, mdx_model_params, song_id, is_webui, input_type, None)
        else:
            orig_song_path, instrumentals_path, main_vocals_dereverb_path, backup_vocals_path = paths

    destination_path = os.path.join('../static/public/ai_cover_gen/', os.path.basename(vocals_path))
    shutil.copy(vocals_path, destination_path)

    return str(destination_path).replace("../", "")


def free_gpu():
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    import gc;
    gc.collect()
    return

def write_file_from_s3(url, destination_path: str = "../rvc_models/default_voice"):
    response = requests.get(url)

    parsed_url = urlparse(url)
    filename = unquote(parsed_url.path.split('/')[-1])
    file_path = os.path.join(destination_path, filename)
    print(file_path)
    if response.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(response.content)
        print("Download completed successfully.")
    else:
        raise Exception(f"Can't download file '{url}' from s3")
