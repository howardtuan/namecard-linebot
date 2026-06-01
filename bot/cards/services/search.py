from django.db.models import Q, QuerySet

from cards.models import BusinessCard, LineUser


SEARCH_FIELDS = [
    "name",
    "company",
    "title",
    "email",
    "phone",
    "address",
    "website",
    "note",
    "raw_text",
    "normalized_text",
    "tags__name",
]


def search_cards(user: LineUser, keyword: str = "", limit: int = 10) -> QuerySet[BusinessCard]:
    cards = user.cards.prefetch_related("tags")
    keyword = keyword.strip()

    if keyword:
        query = Q()
        for field in SEARCH_FIELDS:
            query |= Q(**{f"{field}__icontains": keyword})
        cards = cards.filter(query).distinct()

    return cards[:limit]
