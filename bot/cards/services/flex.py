from urllib.parse import quote

from django.conf import settings
from linebot.models import BubbleContainer, CarouselContainer, FlexSendMessage

from cards.models import BusinessCard

ACCENT = "#0F766E"
INK = "#111827"
MUTED = "#6B7280"
SOFT = "#F8FAFC"
LINE = "#E5E7EB"


def card_alt_text(card: BusinessCard) -> str:
    title = card.name or card.company or "未命名名片"
    subtitle = card.display_title or card.email or card.phone
    return f"{title}｜{subtitle}" if subtitle else title


def build_card_flex_message(card: BusinessCard) -> FlexSendMessage:
    return FlexSendMessage(
        alt_text=card_alt_text(card),
        contents=BubbleContainer.new_from_json_dict(build_card_bubble(card)),
    )


def build_cards_flex_message(cards: list[BusinessCard], alt_text: str = "名片搜尋結果") -> FlexSendMessage:
    bubbles = [build_card_bubble(card, compact=True) for card in cards[:10]]
    if len(bubbles) == 1:
        contents = BubbleContainer.new_from_json_dict(bubbles[0])
    else:
        contents = CarouselContainer.new_from_json_dict({"type": "carousel", "contents": bubbles})
    return FlexSendMessage(alt_text=alt_text, contents=contents)


def build_card_bubble(card: BusinessCard, compact: bool = False) -> dict:
    body_contents = [
        {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": card.name or "未命名名片",
                    "weight": "bold",
                    "size": "xl" if not compact else "lg",
                    "color": INK,
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": card.display_title or "尚未辨識公司/職稱",
                    "size": "sm",
                    "color": MUTED,
                    "wrap": True,
                },
            ],
        },
        {"type": "separator", "margin": "lg", "color": LINE},
    ]

    for label, value in _card_rows(card):
        body_contents.append(_info_row(label, value))

    if card.note and not compact:
        body_contents.extend(
            [
                {"type": "separator", "margin": "lg", "color": LINE},
                {
                    "type": "text",
                    "text": card.note,
                    "size": "sm",
                    "color": MUTED,
                    "wrap": True,
                    "margin": "lg",
                },
            ]
        )

    tag_names = [tag.name for tag in card.tags.all()]
    if tag_names:
        body_contents.append(_tag_row(tag_names))

    bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "backgroundColor": SOFT,
            "contents": body_contents,
        },
    }

    hero_url = _image_url(card)
    if hero_url and not compact:
        bubble["hero"] = {
            "type": "image",
            "url": hero_url,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }

    footer_contents = _footer_buttons(card)
    if footer_contents:
        bubble["footer"] = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": footer_contents,
        }

    return bubble


def _card_rows(card: BusinessCard) -> list[tuple[str, str]]:
    rows = [
        ("電話", card.phone),
        ("Email", card.email),
        ("網站", card.website),
        ("地址", card.address),
    ]
    return [(label, value) for label, value in rows if value]


def _info_row(label: str, value: str) -> dict:
    return {
        "type": "box",
        "layout": "baseline",
        "spacing": "md",
        "margin": "md",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "xs",
                "color": ACCENT,
                "weight": "bold",
                "flex": 2,
            },
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "color": INK,
                "wrap": True,
                "flex": 5,
            },
        ],
    }


def _tag_row(tag_names: list[str]) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "margin": "lg",
        "contents": [
            {
                "type": "text",
                "text": f"#{tag}",
                "size": "xs",
                "color": ACCENT,
                "wrap": True,
            }
            for tag in tag_names[:4]
        ],
    }


def _footer_buttons(card: BusinessCard) -> list[dict]:
    buttons = []
    if card.phone:
        phone = card.phone.split("/")[0].strip().replace(" ", "")
        buttons.append(_button("撥號", f"tel:{phone}"))
    if card.email:
        buttons.append(_button("寄信", f"mailto:{card.email}"))
    if card.website:
        buttons.append(_button("網站", card.website))
    return buttons[:3]


def _button(label: str, uri: str) -> dict:
    return {
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {
            "type": "uri",
            "label": label,
            "uri": uri if uri.startswith(("http", "mailto:", "tel:")) else quote(uri, safe=":/?=&%#@+"),
        },
    }


def _image_url(card: BusinessCard) -> str:
    if not settings.PUBLIC_BASE_URL.startswith("https://") or not card.image:
        return ""
    return f"{settings.PUBLIC_BASE_URL}{card.image.url}"
