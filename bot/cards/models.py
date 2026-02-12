from django.db import models

# Create your models here.

class LineUser(models.Model):
    line_user_id = models.CharField(max_length=64,unique=True,db_index=True)
    display_name = models.CharField(max_length=100,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str: # 後台/console 顯示字串
        return self.display_name or self.line_user_id # 優先顯示名稱，沒有就顯示 line_user_id

class CardTag(models.Model):# 名片標籤資料表（例如：客戶、供應商）
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:  # 後台/console 顯示字串
        return self.name # 顯示標籤名稱

class BusinessCard(models.Model):  # 名片主資料表
    owner = models.ForeignKey(LineUser, on_delete=models.CASCADE, related_name="cards")  # 名片擁有者；使用者刪除時其名片一併刪除
    image = models.ImageField(upload_to="business_cards/%Y/%m/%d/")  # 名片圖片檔，依年/月/日分目錄存放

    # Parsed fields (OCR or manual input)
    name = models.CharField(max_length=100, blank=True)  # 姓名，可留空
    company = models.CharField(max_length=150, blank=True)  # 公司名稱，可留空
    title = models.CharField(max_length=100, blank=True)  # 職稱，可留空
    email = models.EmailField(blank=True)  # Email，可留空（Django 會做基本格式驗證）
    phone = models.CharField(max_length=50, blank=True)  # 電話，可留空
    address = models.CharField(max_length=255, blank=True)  # 地址，可留空
    website = models.URLField(blank=True)  # 網址，可留空（Django 會做基本格式驗證）
    note = models.TextField(blank=True)  # 備註，可留空

    # Optional raw OCR text
    raw_text = models.TextField(blank=True)  # OCR 原始辨識文字，方便除錯或二次解析

    tags = models.ManyToManyField(CardTag, blank=True, related_name="cards")  # 多對多標籤；一張名片可有多標籤，標籤可對多張名片

    created_at = models.DateTimeField(auto_now_add=True)  # 建立時間
    updated_at = models.DateTimeField(auto_now=True)  # 更新時間

    class Meta:  # 模型中繼設定
        ordering = ["-created_at"]  # 預設查詢排序：最新建立的名片在前
        indexes = [
            models.Index(fields=["owner", "-created_at"]),  # 常見查詢：某使用者的最新名片
            models.Index(fields=["name"]),  # 依姓名搜尋加速
            models.Index(fields=["company"]),  # 依公司搜尋加速
            models.Index(fields=["email"]),  # 依 email 搜尋加速
        ]

    def __str__(self) -> str:  # 後台/console 顯示字串
        if self.name and self.company:  # 若姓名與公司都有
            return f"{self.name} ({self.company})"  # 顯示：姓名（公司）
        if self.name:  # 只有姓名
            return self.name  # 顯示姓名
        return f"Card #{self.pk}"  # 都沒有時顯示資料主鍵 ID
    

class ChatSession(models.Model):
    user = models.OneToOneField(LineUser, on_delete=models.CASCADE, related_name="chat_session")
    waiting_parrot_answer = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.line_user_id} ({'waiting' if self.waiting_parrot_answer else 'idle'})"