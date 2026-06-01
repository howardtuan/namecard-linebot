import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class CardExtractionError(RuntimeError):
    """Raised when the AI provider cannot return usable card data."""


@dataclass(frozen=True)
class ExtractedCard:
    name: str = ""
    company: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    website: str = ""
    note: str = ""
    raw_text: str = ""
    tags: tuple[str, ...] = ()
    raw_json: dict[str, Any] | None = None


EXTRACTION_PROMPT = """
你是一個嚴謹的名片 OCR 與資料整理助理。請辨識這張名片，並只回傳一個 JSON object。

規則：
- 不要輸出 Markdown、程式碼區塊、解釋文字或前後綴。
- 看不到或不確定的欄位請填空字串，不要臆測。
- 姓名、公司、職稱請保留原名片語言；電話可保留多組並用「 / 」分隔。
- website 若只有網域，請補成 https:// 開頭。
- note 放入其他有用資訊，例如部門、分機、LINE ID、社群帳號。
- tags 請給 0 到 5 個短標籤，例如產業、角色、地區或語言。

JSON 欄位：
{
  "name": "",
  "company": "",
  "title": "",
  "email": "",
  "phone": "",
  "address": "",
  "website": "",
  "note": "",
  "raw_text": "",
  "tags": []
}
""".strip()


def extract_business_card(image_path: str | Path) -> ExtractedCard:
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        raise CardExtractionError("GOOGLE_API_KEY or GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    try:
        uploaded_file = client.files.upload(file=str(image_path))
        response = client.models.generate_content(
            model=settings.GEMMA_MODEL,
            contents=[uploaded_file, EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(
                temperature=0.1,
                system_instruction="Return compact, valid JSON only.",
            ),
        )
    except Exception as exc:  # pragma: no cover - covered through integration only
        logger.exception("Gemma card extraction failed")
        raise CardExtractionError(str(exc)) from exc

    data = parse_json_object(response.text or "")
    return normalize_card_data(data)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise CardExtractionError("AI response did not contain a JSON object.")
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise CardExtractionError("AI response JSON could not be parsed.") from exc

    if not isinstance(data, dict):
        raise CardExtractionError("AI response JSON root must be an object.")
    return data


def normalize_card_data(data: dict[str, Any]) -> ExtractedCard:
    def clean(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " / ".join(clean(item) for item in value if clean(item))
        return str(value).strip()

    website = clean(data.get("website"))
    if website and not re.match(r"^https?://", website, re.IGNORECASE):
        website = f"https://{website}"

    tags_value = data.get("tags") or []
    if isinstance(tags_value, str):
        tags = tuple(tag.strip() for tag in re.split(r"[,，、/]", tags_value) if tag.strip())
    elif isinstance(tags_value, list):
        tags = tuple(clean(tag) for tag in tags_value if clean(tag))
    else:
        tags = ()

    return ExtractedCard(
        name=clean(data.get("name")),
        company=clean(data.get("company")),
        title=clean(data.get("title")),
        email=clean(data.get("email")),
        phone=clean(data.get("phone")),
        address=clean(data.get("address")),
        website=website,
        note=clean(data.get("note")),
        raw_text=clean(data.get("raw_text")),
        tags=tags[:5],
        raw_json=data,
    )
