import os, uuid, json, shutil, subprocess, threading, re
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT=Path(__file__).parent
DATA=ROOT/"data"; UPLOADS=DATA/"uploads"; OUTPUTS=DATA/"outputs"; JOBS=DATA/"jobs"
for p in (UPLOADS, OUTPUTS, JOBS): p.mkdir(parents=True, exist_ok=True)

app=FastAPI(title="AI Auto Shorts Agent")
app.mount("/static", StaticFiles(directory=ROOT/"static"), name="static")

def run(cmd):
    p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode: raise RuntimeError(p.stderr[-2500:])
    return p.stdout

def ffprobe_duration(path):
    out=run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)])
    return float(out.strip())

def transcribe(path):
    # Optional faster-whisper. If not installed, split the video into evenly spaced candidate windows.
    try:
        from faster_whisper import WhisperModel
        model=WhisperModel(os.getenv("WHISPER_MODEL","base"), device="cpu", compute_type="int8")
        segments, info=model.transcribe(str(path), vad_filter=True)
        return [{"start":float(s.start),"end":float(s.end),"text":s.text.strip()} for s in segments if s.text.strip()]
    except ImportError:
        return []

def choose_windows(segments, duration, clip_len, max_clips):
    if not segments:
        # Safe fallback: evenly spaced excerpts. Install faster-whisper for transcript-aware selection.
        count=min(max_clips, max(1, int(duration//max(clip_len,1))))
        starts=[max(0, min(duration-clip_len, (i+0.5)*duration/count-clip_len/2)) for i in range(count)]
        return [{"start":s,"end":min(duration,s+clip_len),"text":"Auto-selected excerpt"} for s in starts]
    exciting=re.compile(r"\b(wow|amazing|secret|why|how|important|mistake|truth|best|worst|never|always|surprise|लेकिन|क्यों|कैसे|सच|गलती|जरूरी|कमाल|देखिए|ध्यान)\b",re.I)
    candidates=[]
    for i,seg in enumerate(segments):
        start=max(0,seg["start"]-2)
        end=min(duration,start+clip_len)
        if end-start < min(12,clip_len*0.55): continue
        nearby=" ".join(x["text"] for x in segments if x["start"]<end and x["end"]>start)
        words=len(nearby.split())
        score=min(words/45,2.0)+len(exciting.findall(nearby))*0.7
        if words>=8: candidates.append((score,start,end,nearby))
    candidates.sort(reverse=True)
    selected=[]
    for score,start,end,txt in candidates:
        if all(abs(start-x["start"])>clip_len*0.8 for x in selected):
            selected.append({"start":start,"end":end,"text":txt[:500]})
        if len(selected)>=max_clips: break
    return sorted(selected,key=lambda x:x["start"]) or choose_windows([],duration,clip_len,max_clips)

def make_clip(src, out, start, length, index):
    # 9:16 center crop; scale fills 1080x1920.
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    run(["ffmpeg","-y","-ss",str(start),"-i",str(src),"-t",str(length),
         "-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23",
         "-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)])

def process_job(job_id, src, clip_len, max_clips):
    meta_path=JOBS/f"{job_id}.json"
    meta=json.loads(meta_path.read_text())
    try:
        meta["status"]="processing"; meta_path.write_text(json.dumps(meta))
        duration=ffprobe_duration(src)
        segments=transcribe(src)
        windows=choose_windows(segments,duration,clip_len,max_clips)
        folder=OUTPUTS/job_id; folder.mkdir(exist_ok=True)
        clips=[]
        for n,w in enumerate(windows,1):
            out=folder/f"short_{n:02d}.mp4"
            make_clip(src,out,w["start"],w["end"]-w["start"],n)
            clips.append({"name":out.name,"start":round(w["start"],1),"end":round(w["end"],1),"text":w["text"]})
            meta["clips"]=clips; meta_path.write_text(json.dumps(meta))
        meta.update(status="completed",duration=round(duration,1),clips=clips,
                    note=("Transcript-aware selection" if segments else "Fallback: evenly spaced cuts. Install faster-whisper for transcript-aware selection."))
    except Exception as e:
        meta.update(status="failed",error=str(e))
    meta_path.write_text(json.dumps(meta))

@app.get("/",response_class=HTMLResponse)
def home():
    return (ROOT/"static/index.html").read_text()

@app.post("/api/jobs")
async def create_job(video: UploadFile=File(...), clip_seconds:int=Form(45), max_clips:int=Form(5)):
    if not video.filename: raise HTTPException(400,"Video filename missing")
    ext=Path(video.filename).suffix.lower()
    if ext not in {".mp4",".mov",".mkv",".webm",".m4v"}: raise HTTPException(400,"Supported: MP4, MOV, MKV, WEBM, M4V")
    if clip_seconds not in range(15,91): raise HTTPException(400,"Clip duration must be 15–90 seconds")
    if max_clips not in range(1,16): raise HTTPException(400,"Choose 1–15 clips")
    job_id=uuid.uuid4().hex[:12]
    dest=UPLOADS/f"{job_id}{ext}"
    with dest.open("wb") as f: shutil.copyfileobj(video.file,f)
    meta={"id":job_id,"status":"queued","filename":video.filename,"clips":[]}
    (JOBS/f"{job_id}.json").write_text(json.dumps(meta))
    threading.Thread(target=process_job,args=(job_id,str(dest),clip_seconds,max_clips),daemon=True).start()
    return meta

@app.get("/api/jobs/{job_id}")
def job_status(job_id:str):
    p=JOBS/f"{job_id}.json"
    if not p.exists(): raise HTTPException(404,"Job not found")
    return json.loads(p.read_text())

@app.get("/api/jobs/{job_id}/clips/{filename}")
def download_clip(job_id:str,filename:str):
    path=OUTPUTS/job_id/Path(filename).name
    if not path.exists(): raise HTTPException(404,"Clip not ready")
    return FileResponse(path,media_type="video/mp4",filename=path.name)
