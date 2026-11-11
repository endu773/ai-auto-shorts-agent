# AI Auto Shorts Agent — MVP

A first working website prototype: upload a long video, choose clip length and count, then download automatically generated 9:16 MP4 clips.

## Features in this MVP
- Video upload (MP4, MOV, MKV, WEBM, M4V)
- Background processing job
- 9:16 vertical center crop (1080x1920)
- Optional transcript-aware selection with Faster-Whisper
- Fallback evenly spaced excerpts if Faster-Whisper is not installed
- Download each generated MP4

## Important limitations
This is the first development milestone, not yet a production viral-clip intelligence system. The fallback mode does not understand the video; it cuts evenly spaced excerpts. Transcript-aware selection ranks speech segments using a lightweight heuristic, not a trained virality predictor. Captions, speaker-aware reframing, face tracking, music, login, cloud storage, queue workers and multi-user scaling are planned next.

## Run locally
Requires Python 3.11+ and FFmpeg installed.
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000`.

## Docker
```bash
docker build -t ai-auto-shorts .
docker run -p 8000:8000 -v "$PWD/data:/app/data" ai-auto-shorts
```

## Android note
You can test the website from an Android browser after deploying it to a server. Heavy video processing should run on a cloud server, not inside the phone browser. Do not deploy publicly without adding authentication, upload limits, storage cleanup, HTTPS and job isolation.
