from django.test import TestCase, override_settings

from .models import BusinessCard, CardTag, LineUser
from .services.flex import build_card_bubble, build_cards_flex_message
from .services.gemma import normalize_card_data, parse_json_object
from .services.search import search_cards


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

    @override_settings(PUBLIC_BASE_URL="")
    def test_build_cards_flex_message_supports_single_result(self):
        user = LineUser.objects.create(line_user_id="U123")
        card = BusinessCard.objects.create(owner=user, name="Grace Hopper")

        message = build_cards_flex_message([card])

        self.assertEqual(message.type, "flex")
        self.assertEqual(message.alt_text, "名片搜尋結果")
