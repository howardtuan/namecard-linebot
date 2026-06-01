# Django AI 名片辨識 LINE Bot

使用者上傳一張名片照片後，LINE Bot 會用 Google AI Studio 的 Gemma 模型辨識名片資訊，存入 PostgreSQL，並回傳一張簡潔的 LINE Flex 虛擬名片。之後使用者可以輸入關鍵字查詢自己的名片資料。

教學題目可用：

> Django 實戰｜打造 AI 名片辨識 LINE Bot：Gemma、PostgreSQL、Docker 容器化與 Zeabur 部署完整教學

## 功能

- LINE Webhook 簽章驗證
- 支援圖片訊息：下載名片圖片、呼叫 Gemma 視覺模型、儲存辨識結果
- 支援文字查詢：姓名、公司、職稱、Email、電話、地址、網站、備註、標籤
- LINE Flex Message：單張名片圖卡與搜尋結果 carousel
- Django Admin 管理名片與標籤
- PostgreSQL、Docker Compose、本機測試與 Zeabur 部署準備

## 專案結構

```text
.
├── bot/
│   ├── settings.py          # Django settings
│   ├── urls.py
│   └── wsgi.py
├── cards/                   # 名片 app
│   ├── services/
│   │   ├── flex.py          # LINE Flex JSON
│   │   ├── gemma.py         # Google AI Studio / Gemma 辨識
│   │   └── search.py        # 名片搜尋
│   ├── models.py
│   └── views.py             # LINE webhook
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── manage.py
└── requirements.txt
```

## 事前準備

1. LINE Developers 建立 Messaging API channel，取得：
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
2. Google AI Studio 建立 Gemini API key，填到：
   - `GOOGLE_API_KEY`
3. 本機開發若要讓 LINE 打到 webhook，可用 ngrok、Cloudflare Tunnel 或 Zeabur 暫時網域。

## 環境變數

```bash
cp .env.example .env
```

至少填這幾個：

```env
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
GOOGLE_API_KEY=...
PUBLIC_BASE_URL=https://your-public-domain
```

預設模型是 `gemma-4-26b-a4b-it`。想改模型可調整：

```env
GEMMA_MODEL=gemma-4-26b-a4b-it
```

## 本機 Docker 執行

```bash
docker compose up --build
```

服務：

- Django health check: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`
- LINE webhook: `https://your-public-domain/webhook/`

建立管理員：

```bash
docker compose exec web python manage.py createsuperuser
```

停止服務：

```bash
docker compose down
```

連資料庫 volume 一起移除：

```bash
docker compose down -v
```

## LINE 使用方式

- 上傳名片照片：自動辨識、儲存並回傳 Flex 名片
- `/list`：查看最近 10 張名片
- `/search 關鍵字`：搜尋名片
- 直接輸入關鍵字：同樣會搜尋
- `/help`：顯示操作說明

## Zeabur 部署

1. 將 repo 推到 GitHub。
2. 在 Zeabur 建立 Project，加入 PostgreSQL service。
3. 加入此 Django service，選擇從 GitHub repo 部署，使用 Dockerfile。
4. 設定環境變數：

```env
DEBUG=False
DJANGO_SECRET_KEY=請換成長隨機字串
ALLOWED_HOSTS=your-service.zeabur.app
CSRF_TRUSTED_ORIGINS=https://your-service.zeabur.app
PUBLIC_BASE_URL=https://your-service.zeabur.app
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
GOOGLE_API_KEY=...
GEMMA_MODEL=gemma-4-26b-a4b-it
DATABASE_URL=Zeabur PostgreSQL 提供的連線字串
```

5. 部署完成後，到 LINE Developers Console 設定 webhook：

```text
https://your-service.zeabur.app/webhook/
```

並啟用 Webhook、關閉自動回應訊息。

## 本機測試

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
USE_SQLITE=True .venv/bin/python manage.py check
USE_SQLITE=True .venv/bin/python manage.py test cards
```

`USE_SQLITE=True` 只給本機快速測試用；正式執行仍建議使用 PostgreSQL。

## 注意事項

- LINE Flex 的圖片 URL 需要 HTTPS。若 `PUBLIC_BASE_URL` 不是 HTTPS，Flex 卡片會只顯示文字資訊，不放原始名片圖。
- 目前圖片存放在 Django media 目錄。若正式服務需要長期保存原圖，可再接 S3、Cloud Storage 或其他物件儲存。
- AI 辨識不保證 100% 正確，後台可用 Django Admin 修正資料。
