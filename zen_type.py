# -*- coding: utf-8 -*-
"""
ZenType — 離線語音輸入(Typeless 替代品)桌面客戶端

流程:
    按住熱鍵錄音 → 送 SenseVoice 服務(埠 8009)辨識
                 → 套用校正表(corrections.csv,純字串替換)
                 → Qwen 2.5 潤稿(可 F10 開關;逾時就用原文,不卡住)
                 → 複製並 Ctrl+V 貼到游標處

前置需求(需先各自啟動):
    1. SenseVoice 服務  app_sensevoice.py(埠 8009)
    2. Ollama 服務      (埠 11434),且已 `ollama pull` 好設定的模型

依賴套件:
    sounddevice soundfile numpy requests pyperclip keyboard
"""

import sys
import os
import re
import csv
import io
import time
import threading

# --- 主控台改 UTF-8,避免 Windows cp950 印中文/emoji 直接崩潰 ---
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
import pyperclip
import keyboard

# 簡轉繁(台灣標準)。Qwen 是簡體語料為主,潤稿後常變回簡體,
# 用 opencc 決定性地轉回繁體,比叫模型「請用繁體」可靠得多。
try:
    from opencc import OpenCC
    _cc = OpenCC("s2tw")
except Exception as _e:
    _cc = None
    print("[提醒] opencc 載入失敗,將不做簡轉繁:", _e)


def to_traditional(text):
    """把文字轉成繁體(台灣)。opencc 不可用時原樣回傳。"""
    if _cc and text:
        try:
            return _cc.convert(text)
        except Exception:
            return text
    return text


# SenseVoice 的情緒偵測會輸出 😊😔 等 emoji,對輸入法是雜訊,清掉。
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0001F900-\U0001F9FF]"
)
# 中文字與中文標點(用來判斷「兩個中文之間的空白」)
_CJK = r"㐀-䶿一-鿿。，、！？；：「」『』（）〈〉《》……—"


def clean_text(text):
    """清掉 emoji,以及 Qwen 潤稿時在中文字/標點旁硬插入的空白。"""
    text = _EMOJI_RE.sub("", text)
    # 只要空白「前面或後面」是中文字/中文標點就移除(純英文之間的空白會保留)
    text = re.sub(rf"\s+(?=[{_CJK}])|(?<=[{_CJK}])\s+", "", text)
    return text.strip()

# ==================== 設定區(可自行調整)====================
RECORD_KEY        = "right ctrl"    # 按住這個鍵說話,放開送出
TOGGLE_POLISH_KEY = "f10"           # 開 / 關 Qwen 潤稿
QUIT_KEY          = "ctrl+alt+q"    # 結束程式
SENSEVOICE_URL    = "http://127.0.0.1:8009/api/transcribe"
OLLAMA_URL        = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL      = "qwen2.5:3b"    # 若沒抓 3b,改成你有的,例如 "qwen2.5:7b"
POLISH_TIMEOUT    = 8               # Qwen 潤稿逾時(秒);超過就用未潤稿原文
SAMPLE_RATE       = 16000           # SenseVoice 用 16k
POLISH_ENABLED    = True            # 啟動時是否開啟潤稿(隨時可用 F10 切換)

# 決定「程式所在資料夾」:
#   - 打包成 EXE(PyInstaller)後 sys.frozen 為 True,__file__ 會指向暫存解壓目錄,
#     必須改用 sys.executable(EXE 本身)的所在資料夾,才能讀到放在 EXE 旁邊的 corrections.csv。
#   - 一般用 python 執行時,維持原本以 __file__ 為基準。
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORRECTIONS_CSV   = os.path.join(_BASE_DIR, "corrections.csv")
# ===========================================================

# ---- 執行期狀態 ----
_recording = False      # 是否正在錄音
_busy = False           # 是否正在處理上一段(辨識/潤稿/貼字)
_frames = []            # 錄音緩衝
_stream = None          # sounddevice 輸入串流
_corrections = []       # [(誤聽, 正確), ...]


def load_corrections():
    """讀取校正表 CSV(格式:誤聽,正確,備註)。相容 UTF-8 與帶 BOM。"""
    global _corrections
    _corrections = []
    if not os.path.exists(CORRECTIONS_CSV):
        print("[校正表] 找不到 corrections.csv,將略過字串替換。")
        return
    try:
        with open(CORRECTIONS_CSV, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳過標題列(誤聽,正確,備註)
            for row in reader:
                if len(row) >= 2:
                    wrong, correct = row[0].strip(), row[1].strip()
                    if wrong and correct:
                        _corrections.append((wrong, correct))
        print(f"[校正表] 已載入 {len(_corrections)} 筆替換規則。")
    except Exception as e:
        print("[校正表] 讀取失敗:", e)


def apply_corrections(text):
    """對文字套用校正表的字串替換(零延遲、100% 可靠)。"""
    for wrong, correct in _corrections:
        if wrong in text:
            text = text.replace(wrong, correct)
    return text


def _audio_callback(indata, frames_count, time_info, status):
    if _recording:
        _frames.append(indata.copy())


def start_recording():
    """按下熱鍵時開始錄音。用 _recording/_busy 擋掉按鍵自動重複與重入。"""
    global _recording, _frames, _stream
    if _recording or _busy:
        return
    _frames = []
    _recording = True
    try:
        _stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=_audio_callback
        )
        _stream.start()
        print(f"🎙️  錄音中...(放開 [{RECORD_KEY}] 送出)")
    except Exception as e:
        _recording = False
        print("❌ 麥克風啟動失敗:", e)


def stop_recording():
    """放開熱鍵時停止錄音,並丟到背景執行緒處理,避免卡住鍵盤 hook。"""
    global _recording, _stream
    if not _recording:
        return
    _recording = False
    try:
        _stream.stop()
        _stream.close()
    except Exception:
        pass
    _stream = None

    if not _frames:
        print("(沒有錄到聲音)")
        return
    audio = np.concatenate(_frames, axis=0)
    threading.Thread(target=process_audio, args=(audio,), daemon=True).start()


def transcribe(wav_bytes):
    """把 wav 音檔位元組送給 SenseVoice 服務,回傳辨識文字。"""
    files = {"file": ("voice.wav", wav_bytes, "audio/wav")}
    r = requests.post(SENSEVOICE_URL, files=files, timeout=30)
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


def polish(text):
    """用 Ollama 的 Qwen 做潤稿(去贅字、整句)。逾時/失敗由呼叫端 fallback。"""
    prompt = (
        "你是中文口語轉書面的潤稿助手。把下面這段語音辨識逐字稿整理成通順、乾淨的文字:\n"
        "- 去掉「嗯、啊、那個、就是」等口頭禪與重複贅字\n"
        "- 修正明顯錯字與標點\n"
        "- 請務必用繁體中文(台灣)輸出\n"
        "- 不要新增內容、不要改變原意、不要加任何說明或前後綴\n"
        "- 只輸出整理後的文字本身\n"
        f"逐字稿:「{text}」"
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",   # 讓模型常駐記憶體 30 分鐘,避免每次重載
        "options": {"temperature": 0.2},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=POLISH_TIMEOUT)
    r.raise_for_status()
    out = (r.json().get("response") or "").strip()
    out = out.strip("「」\"' \n\t")   # 去掉模型可能多包的引號
    return out or text


def paste_text(text):
    """複製到剪貼簿並送 Ctrl+V 貼到游標處,事後還原原本剪貼簿內容。"""
    prev = ""
    try:
        prev = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    time.sleep(0.15)
    try:
        pyperclip.copy(prev)   # 還原使用者原本的剪貼簿
    except Exception:
        pass


def process_audio(audio):
    """背景執行緒:辨識 → 校正表 → 潤稿 → 校正表 → 貼字。"""
    global _busy
    _busy = True
    try:
        # numpy int16 → 記憶體中的 wav 位元組(不落地成檔)
        buf = io.BytesIO()
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        buf.seek(0)
        wav_bytes = buf.read()

        try:
            text = transcribe(wav_bytes)
        except Exception as e:
            print("❌ 辨識失敗(SenseVoice 服務 8009 沒開?):", e)
            return
        if not text:
            print("(辨識結果為空)")
            return
        print("📝 辨識:", text)

        # 先套校正表 → 讓 Qwen 看到正確的專有名詞
        text = apply_corrections(text)

        if POLISH_ENABLED:
            try:
                text = polish(text)
            except Exception as e:
                print(f"⏱️  潤稿略過(逾時或失敗,改用原文):{e}")

        # 潤稿常把繁體變回簡體 → 決定性地轉回繁體(台灣)
        text = to_traditional(text)
        # 清掉 emoji 與模型硬插的空白
        text = clean_text(text)
        # 最後再套一次校正表 → 此時才與繁體專有名詞比對得到,確保不被模型改回錯字
        text = apply_corrections(text)

        print("📋 輸出:", text)   # 這才是真正貼出去的內容
        paste_text(text)
        print("✅ 已貼到游標處\n")
    finally:
        _busy = False


def toggle_polish():
    global POLISH_ENABLED
    POLISH_ENABLED = not POLISH_ENABLED
    print(f"🔁 Qwen 潤稿已{'開啟' if POLISH_ENABLED else '關閉'}")


def warm_up_model():
    """啟動時先送一個極短請求預熱模型,把第一次辨識的冷啟動卡頓消掉。"""
    try:
        requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": "你好", "stream": False,
                  "keep_alive": "30m", "options": {"num_predict": 1}},
            timeout=120,
        )
        print("🔥 潤稿模型已預熱完成,首次輸入不再卡頓。")
    except Exception as e:
        print("(模型預熱略過,不影響使用):", e)


def main():
    print("=" * 54)
    print(" ZenType 離線語音輸入 已啟動")
    print(f"   按住 [{RECORD_KEY}] 說話,放開自動辨識並貼字")
    print(f"   [{TOGGLE_POLISH_KEY}] 開關 Qwen 潤稿(目前:{'開' if POLISH_ENABLED else '關'})")
    print(f"   [{QUIT_KEY}] 結束程式")
    print(f"   辨識服務:{SENSEVOICE_URL}")
    print(f"   潤稿模型:{OLLAMA_MODEL}(逾時 {POLISH_TIMEOUT}s 則用原文)")
    print("=" * 54)
    load_corrections()

    # 背景預熱潤稿模型(不擋啟動)
    if POLISH_ENABLED:
        threading.Thread(target=warm_up_model, daemon=True).start()

    # 用 press/release 實現「按住說話」;on_press 會因鍵盤自動重複重複觸發,
    # 已在 start_recording 內用 _recording 旗標擋掉。
    keyboard.on_press_key(RECORD_KEY, lambda e: start_recording())
    keyboard.on_release_key(RECORD_KEY, lambda e: stop_recording())
    keyboard.add_hotkey(TOGGLE_POLISH_KEY, toggle_polish)
    keyboard.add_hotkey(QUIT_KEY, lambda: os._exit(0))

    keyboard.wait()  # 阻塞主執行緒,保持常駐


if __name__ == "__main__":
    main()
