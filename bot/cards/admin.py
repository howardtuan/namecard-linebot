from django.contrib import admin

from .models import BusinessCard, CardTag, ChatSession, LineUser


@admin.register(LineUser)
class LineUserAdmin(admin.ModelAdmin):
    list_display = ("display_name", "line_user_id", "created_at", "updated_at")
    search_fields = ("display_name", "line_user_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CardTag)
class CardTagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(BusinessCard)
class BusinessCardAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "title", "email", "phone", "owner", "created_at")
    list_filter = ("tags", "extraction_model", "created_at")
    search_fields = (
        "name",
        "company",
        "title",
        "email",
        "phone",
        "address",
        "note",
        "raw_text",
        "tags__name",
    )
    readonly_fields = ("created_at", "updated_at", "normalized_text", "raw_json")
    filter_horizontal = ("tags",)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "last_query", "updated_at")
    search_fields = ("user__display_name", "user__line_user_id", "last_query")
