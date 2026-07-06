# -*- coding: utf-8 -*-
"""
ZenType 本地語音辨識服務(SenseVoice / FunASR)

- 引擎:阿里 FunAudioLLM 開源 SenseVoiceSmall(非自回歸,中文準、CPU 快,含 fsmn-vad 靜音偵測)
- 對外:POST /api/transcribe(上傳音檔)→ 回 {"text": ..., "raw": ...},埠 8009
- 輸出:opencc 簡→繁(台灣標準)

ZenType 客戶端送的是 16k 單聲道 wav,可直接餵給模型,**不需要 ffmpeg**。
只有當上傳的是 webm/ogg/mp4 等非 wav 格式(例如用瀏覽器測試頁錄音)時,才需要系統有 ffmpeg。

首次啟動會自動從 ModelScope 下載模型(約 900MB,需連網一次),之後可離線使用。
"""

import os
import sys
import uuid
import subprocess

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 隱藏視窗啟動時主控台預設 cp950,輸出中文/emoji 會讓 print 崩潰。統一改 UTF-8 並容錯。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PORT = 8009
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, "_sv_tmp")
os.makedirs(TMP_DIR, exist_ok=True)

app = FastAPI(title="ZenType 本地 SenseVoice 語音辨識服務")

# 允許跨來源(例如瀏覽器測試頁),否則會被瀏覽器擋。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 載入 SenseVoiceSmall(首次執行會自動下載約 900MB,需連網,一次性)
# ==========================================
print("正在載入本地 SenseVoiceSmall 模型(含 fsmn-vad 靜音偵測)...首次啟動會下載模型,請稍候。")
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

# SenseVoice 對中文輸出簡體,用 opencc 轉繁體(台灣標準)。
try:
    from opencc import OpenCC
    _cc = OpenCC("s2tw")
    print("opencc s2tw 簡轉繁已就緒。")
except Exception as e:
    _cc = None
    print("opencc 載入失敗,將輸出原始簡體:", e)

model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
    disable_update=True,  # 啟動時不連網檢查更新,避免卡住
)
print("SenseVoiceSmall 模型載入完成,服務就緒(埠 %d)。" % PORT)


def _resolve_wav(src_path: str, content_type: str) -> str:
    """
    回傳可直接餵給模型的 16k wav 路徑。
    - wav:直接使用(ZenType 客戶端走這條,免 ffmpeg)。
    - 其他格式:用 ffmpeg 轉檔;若系統沒有 ffmpeg 則給清楚提示。
    """
    is_wav = ("wav" in (content_type or "")) or src_path.lower().endswith(".wav")
    if is_wav:
        return src_path
    dst = src_path + ".16k.wav"
    cmd = ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", "-f", "wav", dst]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError(
            "此音檔非 wav,需要 ffmpeg 轉檔,但系統找不到 ffmpeg。"
            "ZenType 客戶端送的是 wav、不需要 ffmpeg;只有瀏覽器測試頁錄音才需安裝 ffmpeg。"
        )
    if proc.returncode != 0 or not os.path.exists(dst):
        err = proc.stderr.decode("utf-8", "replace")[-500:]
        raise RuntimeError("ffmpeg 轉檔失敗: " + err)
    return dst


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    uid = uuid.uuid4().hex
    ct = file.content_type or ""
    ext = "wav"
    if "webm" in ct:
        ext = "webm"
    elif "ogg" in ct:
        ext = "ogg"
    elif "mp4" in ct:
        ext = "mp4"

    src = os.path.join(TMP_DIR, "in_%s.%s" % (uid, ext))
    wav = None
    made_wav = False
    try:
        with open(src, "wb") as f:
            f.write(await file.read())

        wav = _resolve_wav(src, ct)
        made_wav = (wav != src)

        res = model.generate(
            input=wav,
            cache={},
            language="zh",     # 中文最準;要多語可改 "auto"
            use_itn=True,      # 數字/標點正規化
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        raw = res[0]["text"] if res else ""
        text = rich_transcription_postprocess(raw)  # 去除 <|zh|><|NEUTRAL|> 等標籤
        if _cc and text:
            text = _cc.convert(text)  # 簡體→繁體(台灣)
        print("[SenseVoice 辨識]:", text)
        return {"text": text, "raw": raw}
    except Exception as e:
        print("辨識錯誤:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in (src, wav if made_wav else None):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


# 簡易測試頁:載入後可確認服務活著。瀏覽器錄音是 webm,需系統有 ffmpeg;
# ZenType 客戶端則走 wav、不需 ffmpeg。
HTML_CONTENT = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SenseVoice 測試(埠 8009)</title>
<style>
 body{font-family:sans-serif;background:#121212;color:#eee;padding:30px;max-width:680px;margin:auto;}
 .btn{padding:16px 28px;font-size:18px;border:none;border-radius:10px;background:#007bff;color:#fff;cursor:pointer;font-weight:bold;}
 .btn:active{background:#dc3545;} #out{background:#1a1a26;border:1px solid #444;border-radius:10px;padding:18px;font-size:20px;min-height:60px;margin-top:16px;}
 #status{margin:14px 0;color:#00ff88;font-weight:bold;min-height:22px;} .tip{color:#aaa;font-size:14px;margin-top:16px;}
</style></head><body>
 <h1>🎙️ SenseVoice 本地辨識測試(埠 8009)</h1>
 <p class="tip">此頁僅供確認服務是否正常。瀏覽器錄音為 webm,需系統有 ffmpeg;<br>日常用 ZenType 客戶端(送 wav)則不需要 ffmpeg。</p>
 <button class="btn" id="rec">🎙️ 按住說話(放開送出)</button>
 <div id="status">狀態:等待操作...</div>
 <div id="out">(辨識結果會顯示在這裡)</div>
<script>
 let stream=null,recorder=null,chunks=[],mime="audio/webm";
 const rec=document.getElementById('rec'),st=document.getElementById('status'),out=document.getElementById('out');
 async function setup(){
   if(!stream||stream.getTracks().some(t=>t.readyState==='ended'))stream=await navigator.mediaDevices.getUserMedia({audio:true});
   let opt={}; if(MediaRecorder.isTypeSupported('audio/webm')){opt={mimeType:'audio/webm'};mime='audio/webm';}
   else if(MediaRecorder.isTypeSupported('audio/ogg')){opt={mimeType:'audio/ogg'};mime='audio/ogg';}
   recorder=new MediaRecorder(stream,opt);chunks=[];
   recorder.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data);};
   recorder.onstop=async()=>{
     if(!chunks.length)return; st.innerText='⚙️ 辨識中...';
     const blob=new Blob(chunks,{type:mime}); const ext=mime.includes('webm')?'webm':'ogg';
     const fd=new FormData(); fd.append('file',blob,'v.'+ext);
     try{const r=await fetch('/api/transcribe',{method:'POST',body:fd});const d=await r.json();
       out.innerText=d.text||('(錯誤)'+(d.detail||'')); st.innerText='✅ 完成';}
     catch(err){st.innerText='❌ 失敗:'+err;}
   };
 }
 async function start(){try{await setup();if(recorder&&recorder.state==='inactive'){recorder.start();st.innerText='🎙️ 聆聽中...';rec.style.background='#dc3545';}}catch(e){st.innerText='❌ 麥克風啟動失敗';}}
 function stop(){if(recorder&&recorder.state==='recording'){recorder.stop();rec.style.background='#007bff';}}
 rec.addEventListener('mousedown',async e=>{e.preventDefault();await start();});
 rec.addEventListener('mouseup',e=>{e.preventDefault();stop();});
 rec.addEventListener('touchstart',async e=>{e.preventDefault();await start();});
 rec.addEventListener('touchend',e=>{e.preventDefault();stop();});
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTML_CONTENT


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
