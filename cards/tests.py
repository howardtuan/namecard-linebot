from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from linebot.models import ImageMessage, MessageEvent, SourceUser, TextSendMessage
from PIL import Image

from .models import BusinessCard, CardTag, LineUser
from .services.flex import build_card_bubble, build_cards_flex_message
from .services.gemma import CardExtractionError, ExtractedCard, normalize_card_data, parse_json_object
from .services.search import search_cards
from .views import handle_image_message, handle_message_event


class FakeMessageContent:
    def __init__(self, content: bytes):
        self.content = content


class FakeLineBotApi:
    def __init__(self, content: bytes):
        self.content = content
        self.reply_messages = []

    def get_message_content(self, message_id: str) -> FakeMessageContent:
        return FakeMessageContent(self.content)

    def get_profile(self, line_user_id: str) -> SimpleNamespace:
        return SimpleNamespace(display_name="", picture_url="", status_message="")

    def reply_message(self, reply_token: str, message: TextSendMessage) -> None:
        self.reply_messages.append((reply_token, message))


class FakeImageMessage:
    def __init__(self, message_id: str):
        self.id = message_id


class GemmaParsingTests(TestCase):
    def test_parse_json_from_markdown_fence(self):
        data = parse_json_object('```json\n{"name": "Ada", "tags": ["AI"]}\n```')

        self.assertEqual(data["name"], "Ada")
        self.assertEqual(data["tags"], ["AI"])

    def test_normalize_card_data_adds_https_and_joins_lists(self):
        card = normalize_card_data(
            {
                "name": "王小明",
                "phone": ["02-1234-5678", "0912-345-678"],
                "website": "example.com",
                "tags": "科技, 台北",
            }
        )

        self.assertEqual(card.website, "https://example.com")
        self.assertEqual(card.phone, "02-1234-5678 / 0912-345-678")
        self.assertEqual(card.tags, ("科技", "台北"))


class CardSearchTests(TestCase):
    def setUp(self):
        self.user = LineUser.objects.create(line_user_id="U123", display_name="Howard")
        self.other_user = LineUser.objects.create(line_user_id="U999")

        self.card = BusinessCard.objects.create(
            owner=self.user,
            name="王小明",
            company="星河科技",
            title="業務經理",
            email="ming@example.com",
            phone="0912-345-678",
        )
        tag = CardTag.objects.create(name="客戶")
        self.card.tags.add(tag)
        self.card.refresh_normalized_text()
        self.card.save(update_fields=["normalized_text"])

        BusinessCard.objects.create(owner=self.other_user, name="王小明", company="別人的公司")

    def test_search_is_scoped_to_line_user(self):
        results = list(search_cards(self.user, "王小明"))

        self.assertEqual(results, [self.card])

    def test_search_matches_tags(self):
        results = list(search_cards(self.user, "客戶"))

        self.assertEqual(results, [self.card])


class FlexMessageTests(TestCase):
    def test_build_card_bubble_contains_primary_fields(self):
        user = LineUser.objects.create(line_user_id="U123")
        card = BusinessCard.objects.create(
            owner=user,
            name="Ada Lovelace",
            company="Analytical Engines",
            title="Mathematician",
            email="ada@example.com",
        )

        bubble = build_card_bubble(card)
        body_text = str(bubble["body"]["contents"])

        self.assertEqual(bubble["type"], "bubble")
        self.assertIn("Ada Lovelace", body_text)
        self.assertIn("Analytical Engines", body_text)

    @override_settings(PUBLIC_BASE_URL="https://example.com")
    def test_build_card_bubble_omits_original_image_even_if_image_exists(self):
        user = LineUser.objects.create(line_user_id="U123")
        card = BusinessCard.objects.create(
            owner=user,
            name="Ada Lovelace",
            image="business_cards/sample.png",
        )

        bubble = build_card_bubble(card)

        self.assertNotIn("hero", bubble)

    @override_settings(PUBLIC_BASE_URL="")
    def test_build_cards_flex_message_supports_single_result(self):
        user = LineUser.objects.create(line_user_id="U123")
        card = BusinessCard.objects.create(owner=user, name="Grace Hopper")

        message = build_cards_flex_message([card])

        self.assertEqual(message.type, "flex")
        self.assertEqual(message.alt_text, "名片搜尋結果")


class CardImageCleanupTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_dir.name,
            PUBLIC_BASE_URL="https://example.com",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = LineUser.objects.create(line_user_id="U123")

    def test_handle_image_message_deletes_file_after_successful_extraction(self):
        extracted_path = None

        def fake_extract(image_path: str):
            nonlocal extracted_path
            extracted_path = Path(image_path)
            self.assertTrue(extracted_path.exists())
            return ExtractedCard(name="Ada Lovelace", company="Analytical Engines")

        with patch("cards.views.extract_business_card", side_effect=fake_extract):
            reply = handle_image_message(
                FakeLineBotApi(self.png_bytes()),
                self.user,
                FakeImageMessage("MSG1"),
            )

        card = BusinessCard.objects.get(source_message_id="MSG1")

        self.assertEqual(reply.type, "flex")
        self.assertEqual(card.name, "Ada Lovelace")
        self.assertEqual(card.image.name, "")
        self.assertIsNotNone(extracted_path)
        self.assertFalse(extracted_path.exists())
        self.assertNotIn("hero", build_card_bubble(card))

    def test_image_event_replies_with_extracted_flex_card_without_push(self):
        line_bot_api = FakeLineBotApi(self.png_bytes())
        event = MessageEvent(
            reply_token="TOKEN",
            source=SourceUser(user_id="U123"),
            message=ImageMessage(id="MSG1"),
        )

        with patch(
            "cards.views.extract_business_card",
            return_value=ExtractedCard(name="Ada Lovelace", company="Analytical Engines"),
        ):
            handle_message_event(line_bot_api, event)

        card = BusinessCard.objects.get(source_message_id="MSG1")

        self.assertEqual(card.name, "Ada Lovelace")
        self.assertEqual(len(line_bot_api.reply_messages), 1)
        self.assertEqual(line_bot_api.reply_messages[0][0], "TOKEN")
        self.assertEqual(line_bot_api.reply_messages[0][1].type, "flex")

    def test_handle_image_message_deletes_file_after_failed_extraction(self):
        extracted_path = None

        def fake_extract(image_path: str):
            nonlocal extracted_path
            extracted_path = Path(image_path)
            self.assertTrue(extracted_path.exists())
            raise CardExtractionError("boom")

        with patch("cards.views.extract_business_card", side_effect=fake_extract):
            reply = handle_image_message(
                FakeLineBotApi(self.png_bytes()),
                self.user,
                FakeImageMessage("MSG2"),
            )

        card = BusinessCard.objects.get(source_message_id="MSG2")

        self.assertEqual(reply.type, "text")
        self.assertEqual(card.extraction_error, "boom")
        self.assertEqual(card.image.name, "")
        self.assertIsNotNone(extracted_path)
        self.assertFalse(extracted_path.exists())

    def test_handle_image_message_does_not_store_duplicate_message_id(self):
        BusinessCard.objects.create(
            owner=self.user,
            source_message_id="MSG3",
            name="Ada Lovelace",
        )

        with patch("cards.views.extract_business_card") as extract_business_card:
            reply = handle_image_message(
                FakeLineBotApi(self.png_bytes()),
                self.user,
                FakeImageMessage("MSG3"),
            )

        self.assertEqual(reply.type, "flex")
        self.assertEqual(BusinessCard.objects.filter(source_message_id="MSG3").count(), 1)
        extract_business_card.assert_not_called()

    def test_handle_image_message_reuses_incomplete_existing_message_id(self):
        card = BusinessCard.objects.create(owner=self.user, source_message_id="MSG4")

        with patch(
            "cards.views.extract_business_card",
            return_value=ExtractedCard(name="Ada Lovelace", company="Analytical Engines"),
        ):
            reply = handle_image_message(
                FakeLineBotApi(self.png_bytes()),
                self.user,
                FakeImageMessage("MSG4"),
            )

        card.refresh_from_db()

        self.assertEqual(reply.type, "flex")
        self.assertEqual(card.name, "Ada Lovelace")
        self.assertEqual(card.image.name, "")
        self.assertEqual(BusinessCard.objects.filter(source_message_id="MSG4").count(), 1)

    @staticmethod
    def png_bytes() -> bytes:
        buffer = BytesIO()
        Image.new("RGB", (12, 12), color="white").save(buffer, format="PNG")
        return buffer.getvalue()
