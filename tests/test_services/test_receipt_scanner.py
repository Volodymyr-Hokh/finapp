"""Tests for ReceiptScannerService."""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.receipt_scanner import (
    ReceiptScannerService,
    validate_image,
    ImageValidationError,
    ExtractionError,
    ReceiptData,
    ReceiptExtraction,
    MAX_IMAGE_SIZE_BYTES,
)


# Minimal valid file headers for testing
TINY_JPEG = b"\xff\xd8" + b"\x00" * 100
TINY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
TINY_WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100
TINY_GIF = b"GIF89a" + b"\x00" * 100


@pytest.fixture
def mock_openai_client():
    """Create a mock AsyncOpenAI client."""
    return AsyncMock()


@pytest.fixture
def scanner(mock_openai_client):
    """Create scanner with mocked client."""
    return ReceiptScannerService(client=mock_openai_client)


@pytest.fixture
def sample_extraction():
    """Sample valid extraction from OpenAI structured output."""
    return ReceiptExtraction(
        amount="52.30",
        type="expense",
        description="Grocery shopping at Walmart",
        transaction_date="2024-03-15",
        merchant_name="Walmart",
        suggested_category="Groceries",
        suggested_tags=["groceries", "weekly"],
        confidence=0.92,
    )


def _make_openai_response(parsed: ReceiptExtraction):
    """Build a mock OpenAI structured output response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = parsed
    return mock_response


# ---------------------------------------------------------------------------
# Test image validation
# ---------------------------------------------------------------------------


class TestImageValidation:
    def test_valid_jpeg(self):
        mime = validate_image(TINY_JPEG)
        assert mime == "image/jpeg"

    def test_valid_png(self):
        mime = validate_image(TINY_PNG)
        assert mime == "image/png"

    def test_valid_webp(self):
        mime = validate_image(TINY_WEBP)
        assert mime == "image/webp"

    def test_valid_gif(self):
        mime = validate_image(TINY_GIF)
        assert mime == "image/gif"

    def test_rejects_empty_image(self):
        with pytest.raises(ImageValidationError, match="Empty"):
            validate_image(b"")

    def test_rejects_oversized_image(self):
        huge = b"\xff\xd8" + b"\x00" * (MAX_IMAGE_SIZE_BYTES + 1)
        with pytest.raises(ImageValidationError, match="too large"):
            validate_image(huge)

    def test_rejects_unsupported_type(self):
        with pytest.raises(ImageValidationError, match="Unsupported"):
            validate_image(b"\x00\x00\x00\x00" * 100)


# ---------------------------------------------------------------------------
# Test extraction conversion
# ---------------------------------------------------------------------------


class TestExtractionConversion:
    def test_converts_valid_expense(self, scanner, sample_extraction):
        result = scanner._convert_to_receipt_data(sample_extraction)
        assert isinstance(result, ReceiptData)
        assert result.amount == Decimal("-52.30")  # Expense is negative
        assert result.type == "expense"
        assert result.description == "Grocery shopping at Walmart"
        assert result.transaction_date == date(2024, 3, 15)
        assert result.merchant_name == "Walmart"
        assert result.suggested_category == "Groceries"
        assert result.suggested_tags == ["groceries", "weekly"]
        assert result.confidence == 0.92

    def test_income_amount_stays_positive(self, scanner):
        extraction = ReceiptExtraction(
            amount="1000", type="income", description="Salary check", confidence=0.9
        )
        result = scanner._convert_to_receipt_data(extraction)
        assert result.amount == Decimal("1000")
        assert result.type == "income"

    def test_raises_on_zero_amount(self, scanner):
        extraction = ReceiptExtraction(
            amount="0", type="expense", description="Test", confidence=0.5
        )
        with pytest.raises(ExtractionError, match="valid amount"):
            scanner._convert_to_receipt_data(extraction)

    def test_raises_on_invalid_amount(self, scanner):
        extraction = ReceiptExtraction(
            amount="not-a-number", type="expense", description="Test", confidence=0.5
        )
        with pytest.raises(ExtractionError, match="Invalid amount"):
            scanner._convert_to_receipt_data(extraction)

    def test_handles_missing_date(self, scanner):
        extraction = ReceiptExtraction(
            amount="10", type="expense", description="Test", confidence=0.5
        )
        result = scanner._convert_to_receipt_data(extraction)
        assert result.transaction_date is None

    def test_handles_invalid_date(self, scanner):
        extraction = ReceiptExtraction(
            amount="10",
            type="expense",
            description="Test",
            transaction_date="not-a-date",
            confidence=0.5,
        )
        result = scanner._convert_to_receipt_data(extraction)
        assert result.transaction_date is None

    def test_raw_extraction_preserved(self, scanner, sample_extraction):
        result = scanner._convert_to_receipt_data(sample_extraction)
        assert result.raw_extraction == sample_extraction.model_dump_json()


# ---------------------------------------------------------------------------
# Test full extraction with mocked OpenAI
# ---------------------------------------------------------------------------


class TestExtractFromImage:
    @pytest.mark.asyncio
    async def test_successful_extraction(
        self, scanner, mock_openai_client, sample_extraction
    ):
        mock_openai_client.beta.chat.completions.parse.return_value = _make_openai_response(
            sample_extraction
        )

        result = await scanner.extract_from_image(TINY_JPEG, "image/jpeg")

        assert result.amount == Decimal("-52.30")
        assert result.merchant_name == "Walmart"
        mock_openai_client.beta.chat.completions.parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_user_hint(
        self, scanner, mock_openai_client, sample_extraction
    ):
        mock_openai_client.beta.chat.completions.parse.return_value = _make_openai_response(
            sample_extraction
        )

        await scanner.extract_from_image(
            TINY_JPEG, "image/jpeg", user_hint="dinner receipt"
        )

        call_args = mock_openai_client.beta.chat.completions.parse.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        # Should include the hint as a text block
        assert any("dinner receipt" in str(block) for block in user_content)

    @pytest.mark.asyncio
    async def test_no_hint_skips_text_block(
        self, scanner, mock_openai_client, sample_extraction
    ):
        mock_openai_client.beta.chat.completions.parse.return_value = _make_openai_response(
            sample_extraction
        )

        await scanner.extract_from_image(TINY_JPEG, "image/jpeg")

        call_args = mock_openai_client.beta.chat.completions.parse.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[1]["content"]
        # Should only have the image block, no text block
        assert len(user_content) == 1
        assert user_content[0]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_uses_low_temperature(
        self, scanner, mock_openai_client, sample_extraction
    ):
        mock_openai_client.beta.chat.completions.parse.return_value = _make_openai_response(
            sample_extraction
        )

        await scanner.extract_from_image(TINY_JPEG, "image/jpeg")

        call_args = mock_openai_client.beta.chat.completions.parse.call_args
        assert call_args.kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_uses_high_detail(
        self, scanner, mock_openai_client, sample_extraction
    ):
        mock_openai_client.beta.chat.completions.parse.return_value = _make_openai_response(
            sample_extraction
        )

        await scanner.extract_from_image(TINY_JPEG, "image/jpeg")

        call_args = mock_openai_client.beta.chat.completions.parse.call_args
        messages = call_args.kwargs["messages"]
        image_block = messages[1]["content"][0]
        assert image_block["image_url"]["detail"] == "high"

    @pytest.mark.asyncio
    async def test_raises_on_null_parsed(self, scanner, mock_openai_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.parsed = None
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        with pytest.raises(ExtractionError, match="Failed to parse"):
            await scanner.extract_from_image(TINY_JPEG, "image/jpeg")
