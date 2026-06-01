from django.db import models


class LineUser(models.Model):
    line_user_id = models.CharField(max_length=64, unique=True, db_index=True)
    display_name = models.CharField(max_length=100, blank=True)
    picture_url = models.URLField(blank=True)
    status_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.display_name or self.line_user_id


class CardTag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class BusinessCard(models.Model):
    owner = models.ForeignKey(LineUser, on_delete=models.CASCADE, related_name="cards")
    image = models.ImageField(upload_to="business_cards/%Y/%m/%d/")
    source_message_id = models.CharField(max_length=128, blank=True, db_index=True)

    name = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=150, blank=True)
    title = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    note = models.TextField(blank=True)

    raw_text = models.TextField(blank=True)
    raw_json = models.JSONField(blank=True, default=dict)
    normalized_text = models.TextField(blank=True)
    extraction_model = models.CharField(max_length=100, blank=True)
    extraction_error = models.TextField(blank=True)

    tags = models.ManyToManyField(CardTag, blank=True, related_name="cards")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["source_message_id"]),
            models.Index(fields=["name"]),
            models.Index(fields=["company"]),
            models.Index(fields=["title"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        if self.name and self.company:
            return f"{self.name} ({self.company})"
        if self.name:
            return self.name
        if self.company:
            return self.company
        return f"Card #{self.pk}"

    @property
    def display_title(self) -> str:
        parts = [part for part in [self.title, self.company] if part]
        return " / ".join(parts)

    def refresh_normalized_text(self) -> None:
        tag_names = [tag.name for tag in self.tags.all()] if self.pk else []
        values = [
            self.name,
            self.company,
            self.title,
            self.email,
            self.phone,
            self.address,
            self.website,
            self.note,
            self.raw_text,
            " ".join(tag_names),
        ]
        self.normalized_text = "\n".join(value for value in values if value)


class ChatSession(models.Model):
    user = models.OneToOneField(LineUser, on_delete=models.CASCADE, related_name="chat_session")
    last_query = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.line_user_id} ({self.last_query or 'idle'})"
