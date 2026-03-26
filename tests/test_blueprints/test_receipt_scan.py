"""API tests for receipt scan endpoint."""
from decimal import Decimal
from unittest.mock import patch, AsyncMock

import pytest

from services.receipt_scanner import (
    ReceiptData,
    ImageValidationError,
    ExtractionError,
)


# Minimal valid JPEG bytes
TINY_JPEG = b"\xff\xd8" + b"\x00" * 100


@pytest.fixture
def mock_receipt_data():
    return ReceiptData(
        amount=Decimal("-52.30"),
        type="expense",
        description="Groceries at Walmart",
        transaction_date=None,
        suggested_category="Groceries",
        suggested_tags=["groceries"],
        merchant_name="Walmart",
        confidence=0.92,
        raw_extraction='{"amount": "52.30"}',
    )


@pytest.mark.api
class TestScanReceiptEndpoint:
    def test_scan_unauthorized(self, test_client):
        """Test that scanning requires authentication."""
        request, response = test_client.post("/transactions/scan")
        assert response.status_code == 401

    def test_scan_no_image(self, test_client, auth_headers):
        """Test error when no image is provided."""
        request, response = test_client.post(
            "/transactions/scan",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "No image" in response.json["error"]

    def test_scan_successful(self, test_client, auth_headers, mock_receipt_data):
        """Test successful receipt scan with mocked scanner."""
        mock_scanner = AsyncMock()
        mock_scanner.extract_from_image.return_value = mock_receipt_data

        with patch(
            "blueprints.receipt_scan.ReceiptScannerService",
            return_value=mock_scanner,
        ), patch(
            "blueprints.receipt_scan.validate_image",
            return_value="image/jpeg",
        ):
            request, response = test_client.post(
                "/transactions/scan",
                headers=auth_headers,
                data={"hint": "grocery receipt"},
                files={"image": ("receipt.jpg", TINY_JPEG, "image/jpeg")},
            )

        assert response.status_code == 200
        data = response.json
        assert data["amount"] == "-52.30"
        assert data["type"] == "expense"
        assert data["description"] == "Groceries at Walmart"
        assert data["merchant_name"] == "Walmart"
        assert data["confidence"] == 0.92
        assert data["suggested_category"] == "Groceries"
        assert data["suggested_tags"] == ["groceries"]

    def test_scan_invalid_image_type(self, test_client, auth_headers):
        """Test error for unsupported image type."""
        with patch(
            "blueprints.receipt_scan.validate_image",
            side_effect=ImageValidationError(
                "Unsupported image type: application/octet-stream"
            ),
        ):
            request, response = test_client.post(
                "/transactions/scan",
                headers=auth_headers,
                files={"image": ("file.bin", b"\x00" * 100, "application/octet-stream")},
            )

        assert response.status_code == 400
        assert "Unsupported" in response.json["error"]

    def test_scan_oversized_image(self, test_client, auth_headers):
        """Test error for image that is too large."""
        with patch(
            "blueprints.receipt_scan.validate_image",
            side_effect=ImageValidationError("Image too large: 6000000 bytes"),
        ):
            request, response = test_client.post(
                "/transactions/scan",
                headers=auth_headers,
                files={"image": ("big.jpg", TINY_JPEG, "image/jpeg")},
            )

        assert response.status_code == 413
        assert "too large" in response.json["error"].lower()

    def test_scan_extraction_failure(self, test_client, auth_headers):
        """Test error when AI extraction fails."""
        mock_scanner = AsyncMock()
        mock_scanner.extract_from_image.side_effect = ExtractionError(
            "Could not extract a valid amount"
        )

        with patch(
            "blueprints.receipt_scan.ReceiptScannerService",
            return_value=mock_scanner,
        ), patch(
            "blueprints.receipt_scan.validate_image",
            return_value="image/jpeg",
        ):
            request, response = test_client.post(
                "/transactions/scan",
                headers=auth_headers,
                files={"image": ("receipt.jpg", TINY_JPEG, "image/jpeg")},
            )

        assert response.status_code == 400
        assert "Failed to extract" in response.json["error"]

    def test_scan_sets_today_when_no_date(self, test_client, auth_headers):
        """Test that transaction_date defaults to today when not extracted."""
        from datetime import date

        receipt_data = ReceiptData(
            amount=Decimal("-10.00"),
            type="expense",
            description="Coffee",
            transaction_date=None,
            suggested_category=None,
            suggested_tags=[],
            confidence=0.8,
            raw_extraction="{}",
        )

        mock_scanner = AsyncMock()
        mock_scanner.extract_from_image.return_value = receipt_data

        with patch(
            "blueprints.receipt_scan.ReceiptScannerService",
            return_value=mock_scanner,
        ), patch(
            "blueprints.receipt_scan.validate_image",
            return_value="image/jpeg",
        ):
            request, response = test_client.post(
                "/transactions/scan",
                headers=auth_headers,
                files={"image": ("receipt.jpg", TINY_JPEG, "image/jpeg")},
            )

        assert response.status_code == 200
        assert response.json["transaction_date"] == str(date.today())
