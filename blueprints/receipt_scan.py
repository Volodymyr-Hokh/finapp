"""
Receipt/check scanning endpoint.
Upload an image, extract transaction data using AI vision.
"""
from datetime import date

from sanic import Blueprint, Request, json
from sanic_ext import openapi

from schemas.receipt import ReceiptScanResponse
from schemas.shared import ErrorResponse, UnauthorizedResponse
from schemas.enums import TransactionType
from services.auth import protected
from services.receipt_scanner import (
    ReceiptScannerService,
    validate_image,
    ImageValidationError,
    ExtractionError,
)

receipt_scan_bp = Blueprint("ReceiptScan", url_prefix="/transactions")


@receipt_scan_bp.post("/scan")
@openapi.summary("Scan receipt/check image")
@openapi.description("""
Upload a photo of a receipt, check, or invoice. The AI will extract transaction
data (amount, description, date, category suggestion).

Send as multipart/form-data with:
- `image`: The image file (JPEG, PNG, WebP, GIF; max 5 MB)
- `hint` (optional): Text hint about the receipt (e.g., "dinner with friends")

Returns extracted data for user confirmation. Use POST /transactions/ to create
the transaction with the confirmed data.
""")
@openapi.secured("BearerAuth")
@openapi.response(
    200,
    {"application/json": ReceiptScanResponse.model_json_schema()},
    "Scan successful",
)
@openapi.response(
    400,
    {"application/json": ErrorResponse.model_json_schema()},
    "Invalid image or extraction failed",
)
@openapi.response(
    401,
    {"application/json": UnauthorizedResponse.model_json_schema()},
    "Unauthorized",
)
@protected
async def scan_receipt(request: Request):
    """Scan a receipt/check image and extract transaction data."""
    if "image" not in request.files:
        return json(
            {"error": "No image file provided. Use 'image' field in multipart form."},
            status=400,
        )

    uploaded_file = request.files["image"][0]
    image_bytes = uploaded_file.body

    try:
        mime_type = validate_image(image_bytes)
    except ImageValidationError as e:
        status = 413 if "too large" in str(e).lower() else 400
        return json({"error": str(e)}, status=status)

    hint = request.form.get("hint")
    scanner = ReceiptScannerService()

    try:
        receipt_data = await scanner.extract_from_image(
            image_bytes, mime_type, user_hint=hint
        )
    except ExtractionError as e:
        return json(
            {"error": f"Failed to extract data from image: {str(e)}"}, status=400
        )
    except Exception as e:
        return json(
            {"error": f"An error occurred during image processing: {str(e)}"},
            status=500,
        )

    scan_result = ReceiptScanResponse(
        amount=receipt_data.amount,
        type=TransactionType(receipt_data.type),
        description=receipt_data.description,
        transaction_date=receipt_data.transaction_date or date.today(),
        suggested_category=receipt_data.suggested_category,
        suggested_tags=receipt_data.suggested_tags,
        merchant_name=receipt_data.merchant_name,
        confidence=receipt_data.confidence,
    )

    return json(scan_result.model_dump(mode="json"), status=200)
