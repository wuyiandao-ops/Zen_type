# ZenType — 離線語音輸入(Typeless 替代品)

> **English summary** — ZenType is a privacy-first, offline voice dictation tool for
> Windows (Traditional Chinese focused), built as a self-hosted alternative to Typeless.
> Hold a hotkey and speak; on release it runs **local SenseVoice STT → correction-table
> replacement → local Qwen (via Ollama) cleanup → paste at the cursor**. Your audio never
> leaves your machine. It needs a local SenseVoice service (port 8009) and Ollama running.
> See the Chinese guide below for setup. Licensed under MIT.

按住熱鍵說話,放開後自動:**SenseVoice 離線辨識 → 校正表替換 → Qwen 潤稿 → 貼到游標處**。
全程音訊不出你的電腦(只有潤稿走本機 Ollama),隱私、離線、免月費。

> 🚀 **完全沒經驗?** 直接看 **[新手安裝指南.md](新手安裝指南.md)**,照著點就能裝好、用起來。
> 🧭 想了解設計思路與演進,看 **[專案演進.md](專案演進.md)**。

---

## 一、架構(三顆現成零件 + 這支膠水)

```
[右 Ctrl 按住錄音]
      │  音訊(記憶體中的 wav)
      ▼
SenseVoice 服務 (埠 8009)  ── sensevoice_server.py(本專案內含)
      │  辨識文字(已簡轉繁)
      ▼
校正表 corrections.csv     ── 純字串替換,零延遲
      │
      ▼
Qwen 2.5 (Ollama 埠 11434) ── 去贅字、整句;可關、逾時就跳過
      │
      ▼
Ctrl+V 貼到游標所在的任何 App
```

---

## 二、安裝(第一次,一次就好)

> 完全沒經驗的話,請改看 **[新手安裝指南.md](新手安裝指南.md)**(有圖文步驟)。以下是精簡版。

1. 安裝 **Python**(https://www.python.org/downloads/ ,安裝時勾「Add python.exe to PATH」)
2. 安裝 **Ollama**(https://ollama.com/download )
3. 雙擊 **`install.bat`** —— 自動安裝套件、下載 Qwen 與 SenseVoice 模型(約幾 GB,請耐心等)。

> `install.bat` 等同於依序執行:
> `pip install -r requirements.txt` → `ollama pull qwen2.5:3b` → 下載 SenseVoice 模型(約 900MB)。

---

## 三、啟動 ZenType

**方式 A:一鍵啟動(推薦)** — 雙擊 **`start.bat`**,會自動開啟辨識服務(sensevoice_server.py)與客戶端。

**方式 B:手動啟動** — 開兩個視窗分別執行:
```
python sensevoice_server.py   (等它顯示「服務就緒(埠 8009)」)
python zen_type.py
```

### 操作
| 動作 | 按鍵 |
|---|---|
| 按住說話,放開送出並貼字 | **右 Ctrl** |
| 開 / 關 Qwen 潤稿 | **F10** |
| 結束程式 | **Ctrl + Alt + Q** |

---

## 四、校正表 corrections.csv

複製 `corrections.example.csv` 為 `corrections.csv`,再填入你自己的專有名詞。
格式三欄:`誤聽,正確,備註`。用 Excel 或記事本編輯即可,**存檔請用 UTF-8**。
改完重新啟動 ZenType 生效。
(`corrections.csv` 已被 `.gitignore` 排除,不會上傳,你的個人詞彙不外流。)

```
誤聽,正確,備註
華嚴京,華嚴經,
大制度論,大智度論,
```

---

## 五、設定區(zen_type.py 最上方)

| 參數 | 預設 | 說明 |
|---|---|---|
| `RECORD_KEY` | `right ctrl` | 錄音熱鍵 |
| `OLLAMA_MODEL` | `qwen2.5:3b` | 潤稿模型;沒抓 3b 就改成你有的 |
| `POLISH_TIMEOUT` | `8` | 潤稿逾時秒數,超過就用未潤稿原文 |
| `POLISH_ENABLED` | `True` | 啟動時潤稿開/關 |

---

## 六、打包成 EXE(選用)

給不想裝 Python 的人使用時,可打包成單一 EXE:
```
pip install pyinstaller
build_exe.bat
```
產物在 `dist\ZenType.exe`。打包指令已用 `--collect-all opencc/sounddevice/soundfile`
收齊字典與原生 DLL(否則轉繁或錄音會在執行時崩潰)。

**散布時要一起給的東西**:
- `ZenType.exe`
- `corrections.csv`(放在 EXE 同層資料夾)

> 注意:EXE 仍需對方電腦上有 **SenseVoice 服務(8009)** 與 **Ollama** 在執行——
> 辨識引擎與模型無法包進 EXE。EXE 只是免去安裝 Python 這一步。

---

## 七、疑難排解

| 症狀 | 原因 / 解法 |
|---|---|
| 按右 Ctrl 沒反應 | `keyboard` 在某些環境需系統管理員權限 → 用「以系統管理員身分執行」開終端機再跑 |
| 辨識失敗 8009 沒開 | 先啟動 `sensevoice_server.py`(或直接用 `start.bat`),確認看到「服務就緒(埠 8009)」 |
| 潤稿每次都逾時跳過 | 模型太大/機器太慢 → 換 `qwen2.5:1.5b`,或調大 `POLISH_TIMEOUT`,或按 F10 關閉潤稿 |
| 貼上的是舊剪貼簿內容 | 目標程式吃 Ctrl+V 較慢 → 可把 `paste_text` 內的 `time.sleep(0.15)` 調大一點 |
| 中文變亂碼 | 主控台已在程式內設 UTF-8;若仍亂碼,終端機字型/編碼改 UTF-8 |
