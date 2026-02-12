from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from .models import LineUser, ChatSession


line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)


def get_or_create_user_and_session(line_user_id: str):
    user, _ = LineUser.objects.get_or_create(line_user_id=line_user_id)
    session, _ = ChatSession.objects.get_or_create(user=user)
    return user, session


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    signature = request.META.get("HTTP_X_LINE_SIGNATURE", "") #取 LINE 簽章 header，用來驗證這包請求是不是 LINE 送的。
    body = request.body.decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        return HttpResponseBadRequest("Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        line_user_id = event.source.user_id
        text = event.message.text.strip()
        _, session = get_or_create_user_and_session(line_user_id)

        if text == "/parrot":
            session.waiting_parrot_answer = True
            session.save(update_fields=["waiting_parrot_answer", "updated_at"])
            reply_text = "今天心情如何？"
        elif session.waiting_parrot_answer:
            reply_text = f"鸚鵡：你剛剛說「{text}」"
            session.waiting_parrot_answer = False
            session.save(update_fields=["waiting_parrot_answer", "updated_at"])
        else:
            reply_text = "輸入 /parrot 開始一問一答。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return HttpResponse("OK")
