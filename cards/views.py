import logging
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import FlexSendMessage, ImageMessage, MessageEvent, TextMessage, TextSendMessage
from PIL import Image, UnidentifiedImageError

from .models import BusinessCard, CardTag, ChatSession, LineUser
from .services.flex import build_card_flex_message, build_cards_flex_message
from .services.gemma import CardExtractionError, ExtractedCard, extract_business_card
from .services.search import search_cards

logger = logging.getLogger(__name__)

HELP_TEXT = "\n".join(
    [
        "上傳一張名片照片，我會辨識後存成虛擬名片。",
        "查詢方式：",
        "• /list：最近 10 張",
        "• /search 關鍵字：搜尋姓名、公司、職稱、Email、電話、標籤",
        "• 直接輸入關鍵字也可以搜尋",
    ]
)

IMAGE_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def get_line_bot_api() -> LineBotApi:
    if not settings.LINE_CHANNEL_ACCESS_TOKEN:
        raise ImproperlyConfigured("LINE_CHANNEL_ACCESS_TOKEN is not configured.")
    return LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)


def get_webhook_parser() -> WebhookParser:
    if not settings.LINE_CHANNEL_SECRET:
        raise ImproperlyConfigured("LINE_CHANNEL_SECRET is not configured.")
    return WebhookParser(settings.LINE_CHANNEL_SECRET)


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    signature = request.META.get("HTTP_X_LINE_SIGNATURE", "")
    body = request.body.decode("utf-8")

    try:
        events = get_webhook_parser().parse(body, signature)
    except InvalidSignatureError:
        return HttpResponseBadRequest("Invalid signature")
    except ImproperlyConfigured as exc:
        logger.error("Webhook configuration error: %s", exc)
        return HttpResponseServerError("Server configuration error")

    try:
        line_bot_api = get_line_bot_api()
    except ImproperlyConfigured as exc:
        logger.error("Webhook configuration error: %s", exc)
        return HttpResponseServerError("Server configuration error")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        try:
            handle_message_event(line_bot_api, event)
        except Exception:
            logger.exception("Failed to handle LINE event")
            safe_reply(
                line_bot_api,
                event.reply_token,
                TextSendMessage(text="處理時發生錯誤，請稍後再試一次。"),
            )

    return HttpResponse("OK")


def handle_message_event(line_bot_api: LineBotApi, event: MessageEvent) -> None:
    line_user_id = getattr(event.source, "user_id", "")
    if not line_user_id:
        safe_reply(line_bot_api, event.reply_token, TextSendMessage(text="請在一對一聊天室使用名片功能。"))
        return

    user = get_or_create_user(line_bot_api, line_user_id)
    ChatSession.objects.get_or_create(user=user)

    if isinstance(event.message, ImageMessage):
        reply = handle_image_message(line_bot_api, user, event.message)
        safe_reply(line_bot_api, event.reply_token, reply)
        return

    if isinstance(event.message, TextMessage):
        reply = handle_text_message(user, event.message.text)
    else:
        reply = TextSendMessage(text="請上傳名片照片，或輸入關鍵字搜尋名片。")

    safe_reply(line_bot_api, event.reply_token, reply)


def get_or_create_user(line_bot_api: LineBotApi, line_user_id: str) -> LineUser:
    user, _ = LineUser.objects.get_or_create(line_user_id=line_user_id)

    try:
        profile = line_bot_api.get_profile(line_user_id)
    except LineBotApiError:
        return user

    changed_fields = []
    profile_values = {
        "display_name": getattr(profile, "display_name", "") or "",
        "picture_url": getattr(profile, "picture_url", "") or "",
        "status_message": getattr(profile, "status_message", "") or "",
    }
    for field, value in profile_values.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed_fields.append(field)

    if changed_fields:
        user.save(update_fields=changed_fields + ["updated_at"])
    return user


def handle_image_message(line_bot_api: LineBotApi, user: LineUser, message: ImageMessage | str):
    message_id = message if isinstance(message, str) else message.id
    card = BusinessCard.objects.filter(owner=user, source_message_id=message_id).order_by("-created_at").first()
    if card:
        if card.extraction_error:
            return TextSendMessage(text=f"這張名片先前 AI 辨識失敗：{card.extraction_error}")
        if has_extracted_card_data(card):
            return build_card_flex_message(card)

    if not card:
        image_bytes = download_message_content(line_bot_api, message_id)
        mime_type, extension = detect_image_type(image_bytes)
        card = BusinessCard.objects.create(owner=user, source_message_id=message_id)
        filename = f"{user.line_user_id}_{message_id}.{extension}"
        card.image.save(filename, ContentFile(image_bytes), save=True)
    elif not card.image:
        image_bytes = download_message_content(line_bot_api, message_id)
        mime_type, extension = detect_image_type(image_bytes)
        filename = f"{user.line_user_id}_{message_id}.{extension}"
        card.image.save(filename, ContentFile(image_bytes), save=True)

    image_path = card.image.path

    try:
        extracted = extract_business_card(image_path)
    except CardExtractionError as exc:
        card.extraction_error = str(exc)
        card.extraction_model = settings.GEMMA_MODEL
        card.refresh_normalized_text()
        card.save(update_fields=["extraction_error", "extraction_model", "normalized_text", "updated_at"])
        return TextSendMessage(text=f"名片照片已收到，但 AI 辨識失敗：{exc}")
    finally:
        delete_card_image_file(card)

    apply_extracted_card(card, extracted)
    return build_card_flex_message(card)


def has_extracted_card_data(card: BusinessCard) -> bool:
    return any(
        [
            card.name,
            card.company,
            card.title,
            card.email,
            card.phone,
            card.address,
            card.website,
            card.note,
            card.raw_text,
        ]
    )


def handle_text_message(user: LineUser, text: str):
    text = text.strip()
    lower_text = text.lower()

    if lower_text in {"/help", "help", "?", "說明"}:
        return TextSendMessage(text=HELP_TEXT)

    if lower_text in {"/list", "list", "最近", "清單"}:
        cards = list(search_cards(user, limit=10))
        if not cards:
            return TextSendMessage(text="目前還沒有名片。先上傳一張名片照片吧。")
        return build_cards_flex_message(cards, alt_text="最近的名片")

    keyword = text
    if lower_text.startswith("/search "):
        keyword = text[8:].strip()
    elif text.startswith("搜尋 "):
        keyword = text[3:].strip()

    if not keyword:
        return TextSendMessage(text=HELP_TEXT)

    cards = list(search_cards(user, keyword=keyword, limit=10))
    remember_last_query(user, keyword)
    if not cards:
        return TextSendMessage(text=f"找不到「{keyword}」相關名片。")
    return build_cards_flex_message(cards, alt_text=f"搜尋：{keyword}")


def apply_extracted_card(card: BusinessCard, extracted: ExtractedCard) -> None:
    card.name = extracted.name
    card.company = extracted.company
    card.title = extracted.title
    card.email = extracted.email
    card.phone = extracted.phone
    card.address = extracted.address
    card.website = extracted.website
    card.note = extracted.note
    card.raw_text = extracted.raw_text
    card.raw_json = extracted.raw_json or {}
    card.extraction_model = settings.GEMMA_MODEL
    card.extraction_error = ""
    card.save()

    tag_objects = []
    for tag_name in extracted.tags:
        tag, _ = CardTag.objects.get_or_create(name=tag_name[:50])
        tag_objects.append(tag)
    card.tags.set(tag_objects)

    card.refresh_normalized_text()
    card.save(update_fields=["normalized_text", "updated_at"])


def delete_card_image_file(card: BusinessCard) -> None:
    if not card.image:
        return

    image_name = card.image.name
    try:
        card.image.delete(save=False)
    except Exception:
        logger.exception("Failed to delete uploaded business card image: %s", image_name)

    card.image = ""
    card.save(update_fields=["image", "updated_at"])


def remember_last_query(user: LineUser, keyword: str) -> None:
    ChatSession.objects.update_or_create(user=user, defaults={"last_query": keyword[:255]})


def download_message_content(line_bot_api: LineBotApi, message_id: str) -> bytes:
    response = line_bot_api.get_message_content(message_id)
    if hasattr(response, "iter_content"):
        return b"".join(chunk for chunk in response.iter_content() if chunk)
    if hasattr(response, "content"):
        return response.content
    return bytes(response)


def detect_image_type(image_bytes: bytes) -> tuple[str, str]:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            mime_type = Image.MIME.get(image.format, "image/jpeg")
    except UnidentifiedImageError as exc:
        raise ValueError("Uploaded content is not a supported image.") from exc

    return mime_type, IMAGE_MIME_TO_EXT.get(mime_type, "jpg")


def safe_reply(line_bot_api: LineBotApi, reply_token: str, message: TextSendMessage | FlexSendMessage) -> None:
    try:
        line_bot_api.reply_message(reply_token, message)
    except LineBotApiError:
        logger.exception("Failed to reply to LINE")
