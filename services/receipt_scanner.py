"""
Receipt/check scanning service using OpenAI Vision API (GPT-4o).
Extracts transaction data from images of receipts and checks.
"""
import base64
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

import logfire
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from settings import settings

# Constants
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class ReceiptExtraction(BaseModel):
    """Schema for OpenAI structured output extraction."""

    amount: str = Field(description="Decimal amount as string (e.g., '52.30'). Use the TOTAL amount.")
    type: Literal["income", "expense"] = Field(
        description="'expense' for receipts/invoices, 'income' for checks received"
    )
    description: str = Field(description="Brief description (e.g., 'Grocery shopping at Walmart')")
    transaction_date: Optional[str] = Field(
        None, description="Date in YYYY-MM-DD format if visible, or null"
    )
    merchant_name: Optional[str] = Field(None, description="Merchant/store name if visible")
    suggested_category: Optional[str] = Field(
        None,
        description="One of: Food & Dining, Groceries, Transportation, Shopping, Entertainment, "
        "Utilities, Healthcare, Education, Travel, Housing, Insurance, Fitness, Clothing, "
        "Personal Care, Gifts & Donations, Subscriptions, Salary, Investment, Business, Other",
    )
    suggested_tags: list[str] = Field(default_factory=list, description="Relevant tags")
    confidence: float = Field(
        ge=0.0, le=1.0, description="How clearly you can read the document (0.0 to 1.0)"
    )


@dataclass
class ReceiptData:
    """Structured data extracted from a receipt/check image."""

    amount: Decimal
    type: str  # "income" or "expense"
    description: str
    transaction_date: Optional[date]
    suggested_category: Optional[str]
    suggested_tags: list[str] = field(default_factory=list)
    merchant_name: Optional[str] = None
    confidence: float = 0.5
    raw_extraction: str = ""


class ImageValidationError(Exception):
    """Raised when image validation fails."""

    pass


class ExtractionError(Exception):
    """Raised when data extraction from image fails."""

    pass


def _detect_mime_type(data: bytes) -> str:
    """Detect MIME type from file magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


def validate_image(image_bytes: bytes) -> str:
    """
    Validate image size and type. Returns the detected MIME type.
    Raises ImageValidationError on failure.
    """
    if len(image_bytes) == 0:
        raise ImageValidationError("Empty image data")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ImageValidationError(
            f"Image too large: {len(image_bytes)} bytes. "
            f"Maximum allowed: {MAX_IMAGE_SIZE_BYTES} bytes (5 MB)"
        )

    detected_type = _detect_mime_type(image_bytes)
    if detected_type not in ALLOWED_MIME_TYPES:
        raise ImageValidationError(
            f"Unsupported image type: {detected_type}. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    return detected_type


RECEIPT_EXTRACTION_PROMPT = """You are a financial data extraction assistant. Analyze the provided image of a receipt, check, invoice, or similar financial document.

Guidelines:
- Use the TOTAL amount if visible; if not, try to sum up line items
- Default to 'expense' type unless this is clearly a paycheck, income check, or refund
- The confidence should reflect how clearly you can read the document
- Suggest relevant tags based on the merchant and items"""


class ReceiptScannerService:
    """Service for extracting transaction data from receipt/check images."""

    def __init__(self, client: Optional[AsyncOpenAI] = None):
        self.client = client or AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value()
        )

    async def extract_from_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        user_hint: Optional[str] = None,
    ) -> ReceiptData:
        """
        Extract transaction data from a receipt/check image.

        Args:
            image_bytes: Raw image bytes
            mime_type: MIME type of the image
            user_hint: Optional hint from the user about the image

        Returns:
            ReceiptData with extracted information

        Raises:
            ExtractionError: If extraction fails
        """
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        user_content = []
        if user_hint:
            user_content.append({"type": "text", "text": f"User context: {user_hint}"})
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}",
                    "detail": "high",
                },
            }
        )

        with logfire.span("receipt_scanner.extract", mime_type=mime_type):
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": RECEIPT_EXTRACTION_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format=ReceiptExtraction,
                max_tokens=1024,
                temperature=0.1,
            )

        extraction = response.choices[0].message.parsed
        if extraction is None:
            raise ExtractionError("Failed to parse structured output from image")

        return self._convert_to_receipt_data(extraction)

    def _convert_to_receipt_data(self, extraction: ReceiptExtraction) -> ReceiptData:
        """Convert structured extraction to ReceiptData."""
        # Convert amount
        try:
            amount = Decimal(extraction.amount)
            if amount == 0:
                raise ExtractionError("Could not extract a valid amount from the image")
        except InvalidOperation:
            raise ExtractionError(f"Invalid amount value: {extraction.amount}")

        # Parse date
        txn_date = None
        if extraction.transaction_date:
            try:
                txn_date = date.fromisoformat(extraction.transaction_date)
            except ValueError:
                txn_date = None

        # Make expense amounts negative
        if extraction.type == "expense" and amount > 0:
            amount = -amount

        return ReceiptData(
            amount=amount,
            type=extraction.type,
            description=extraction.description,
            transaction_date=txn_date,
            suggested_category=extraction.suggested_category,
            suggested_tags=extraction.suggested_tags,
            merchant_name=extraction.merchant_name,
            confidence=extraction.confidence,
            raw_extraction=extraction.model_dump_json(),
        )
