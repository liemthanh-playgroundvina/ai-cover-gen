from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pydantic import BaseModel, validator
from main import song_cover_pipeline
import asyncio
import os

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("BASE_DIR: ", BASE_DIR)

# static
public_path = "../song_output"
app.mount("/static", StaticFiles(directory=public_path), name="static")


class GenerateCoverRequest(BaseModel):
    youtube_link: str
    artist_name: str

    class Config:
        schema_extra = {
            "example": {
                "youtube_link": "https://www.youtube.com/watch?v=kOCkne-Bku4",
                "artist_name": "Naruto",
            }
        }

    @validator('artist_name')
    def validate_artist(cls, v):
        list_artist = [
            'Naruto', 'Dr. Heinz DoofenShmirtz', 'Spongebob Squarepants', 'Taeyeon',
            'Taylor Swift', 'Wendy', 'Phineas Flynn', 'The Weekend', 'Hatsune Miku',
            'Elon Musk', 'Jungkook', 'Donald Trump', 'Ariana Grande', 'Peter Griffin',
            'Barack Obama', 'Batman', 'Luffy', 'Jisoo', 'Bruno Mars', 'Samuel L. Jackson',
            # Test
            'test_domixi',
        ]

        if v not in list_artist:
            raise ValueError(f"artist_name must be in {list_artist}")
        return v


@app.post("/generate-cover/")
async def generate_cover(request: GenerateCoverRequest):
    """
    Generate a cover song using the provided parameters.
    - youtube_link: A YouTube link
    - artist_name: Name of the Artist, must in [
            'Naruto', 'Dr. Heinz DoofenShmirtz', 'Spongebob Squarepants', 'Taeyeon',
            'Taylor Swift', 'Wendy', 'Phineas Flynn', 'The Weekend', 'Hatsune Miku',
            'Elon Musk', 'Jungkook', 'Donald Trump', 'Ariana Grande', 'Peter Griffin',
            'Barack Obama', 'Batman', 'Luffy', 'Jisoo', 'Bruno Mars', 'Samuel L. Jackson'
        ]
    """

    try:
        _, _, result = await asyncio.to_thread(
            song_cover_pipeline,
            request.youtube_link,
            request.artist_name,
            0,
            False
        )
        url_base = "http://192.168.1.34:8008/static/"
        url_file = url_base + result.split("/song_output/")[-1]
        return {
            "status_code": 200,
            "message": "",
            "data": {"url": url_file}
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if str(e) == "'NoneType' object has no attribute 'setdefault'":
            raise HTTPException(status_code=400, detail=str("Please choose right Youtube link"))
        raise HTTPException(status_code=500, detail=str(e))
