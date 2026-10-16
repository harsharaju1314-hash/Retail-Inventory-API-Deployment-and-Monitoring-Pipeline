import logging
import time
import uuid
from datetime import datetime, timezone
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.database import check_db_connection
from app.models import (
    DuplicateSkuError,
    ProductNotFoundError,
    ProductRepository,
    ValidationError,
)

api_bp = Blueprint("api", __name__)
logger = logging.getLogger("retail_api.routes")


@api_bp.before_request
def start_timer():
    """Assign request ID and record start time for latency tracking."""
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    g.start_time = time.perf_counter()


@api_bp.after_request
def log_request(response):
    """Log structured access details for every incoming HTTP request."""
    # Exclude /health from noisy logging if desired, but logging it is useful for verification
    duration_ms = 0.0
    if hasattr(g, "start_time"):
        duration_ms = round((time.perf_counter() - g.start_time) * 1000, 2)

    req_id = getattr(g, "request_id", "unknown")
    response.headers["X-Request-ID"] = req_id

    extra = {
        "request_id": req_id,
        "method": request.method,
        "path": request.path,
        "status_code": response.status_code,
        "remote_addr": request.remote_addr,
        "duration_ms": duration_ms,
    }

    log_level = logging.INFO
    if response.status_code >= 500:
        log_level = logging.ERROR
    elif response.status_code >= 400:
        log_level = logging.WARNING

    logger.log(
        log_level,
        f"{request.method} {request.path} {response.status_code} - {duration_ms}ms",
        extra=extra,
    )
    return response


@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    Service health check endpoint.
    Verifies SQLite database connectivity and returns system status.
    """
    db_healthy, db_error = check_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not db_healthy:
        logger.error(
            "Health check failed: database unreachable",
            extra={
                "request_id": getattr(g, "request_id", "unknown"),
                "error_details": db_error,
            },
        )
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "timestamp": now_iso,
                    "database": "disconnected",
                    "error": db_error,
                    "version": "1.0.0",
                }
            ),
            503,
        )

    return (
        jsonify(
            {
                "status": "healthy",
                "timestamp": now_iso,
                "database": "connected",
                "version": "1.0.0",
            }
        ),
        200,
    )


@api_bp.route("/products", methods=["GET"])
def list_products():
    """List inventory products with optional category and in_stock filtering."""
    category = request.args.get("category")
    in_stock_param = request.args.get("in_stock")

    in_stock = None
    if in_stock_param is not None:
        if in_stock_param.lower() in ("true", "1", "yes"):
            in_stock = True
        elif in_stock_param.lower() in ("false", "0", "no"):
            in_stock = False
        else:
            return (
                jsonify(
                    {
                        "error": "Bad Request",
                        "message": "Query param 'in_stock' must be 'true' or 'false'.",
                    }
                ),
                400,
            )

    products = ProductRepository.list_products(category=category, in_stock=in_stock)
    return jsonify({"products": products, "count": len(products)}), 200


@api_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id: int):
    """Retrieve details for a single product by ID."""
    try:
        product = ProductRepository.get_by_id(product_id)
        return jsonify({"product": product}), 200
    except ProductNotFoundError as exc:
        return jsonify({"error": "Not Found", "message": str(exc)}), 404


@api_bp.route("/products", methods=["POST"])
def create_product():
    """Add a new product to the retail inventory."""
    if not request.is_json:
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "Content-Type must be 'application/json'.",
                }
            ),
            400,
        )

    data = request.get_json(silent=True)
    if data is None:
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "Malformed JSON payload provided.",
                }
            ),
            400,
        )

    try:
        product = ProductRepository.create(data)
        logger.info(
            f"Created new product: ID {product['id']}, SKU {product['sku']}",
            extra={"request_id": getattr(g, "request_id", "unknown")},
        )
        return jsonify({"product": product}), 201
    except ValidationError as exc:
        return jsonify({"error": "Bad Request", "message": str(exc)}), 400
    except DuplicateSkuError as exc:
        return jsonify({"error": "Conflict", "message": str(exc)}), 409


@api_bp.route("/products/<int:product_id>/stock", methods=["PATCH"])
def update_product_stock(product_id: int):
    """Update stock quantity for an existing product."""
    if not request.is_json:
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "Content-Type must be 'application/json'.",
                }
            ),
            400,
        )

    data = request.get_json(silent=True)
    if data is None:
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "Malformed JSON payload provided.",
                }
            ),
            400,
        )

    try:
        updated = ProductRepository.update_stock(product_id, data)
        logger.info(
            f"Updated stock for product ID {product_id} to {updated['stock_quantity']}",
            extra={"request_id": getattr(g, "request_id", "unknown")},
        )
        return jsonify({"product": updated}), 200
    except ProductNotFoundError as exc:
        return jsonify({"error": "Not Found", "message": str(exc)}), 404
    except ValidationError as exc:
        return jsonify({"error": "Bad Request", "message": str(exc)}), 400


def register_error_handlers(app):
    """Register standard JSON error handlers across the application."""

    @app.errorhandler(400)
    def bad_request(error):
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": getattr(error, "description", "Invalid request syntax or parameters."),
                }
            ),
            400,
        )

    @app.errorhandler(404)
    def not_found(error):
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": getattr(error, "description", "Requested resource was not found."),
                }
            ),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(error):
        return (
            jsonify(
                {
                    "error": "Method Not Allowed",
                    "message": "HTTP method not supported for this endpoint.",
                }
            ),
            405,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        # Allow standard HTTP exceptions to preserve their status code
        if isinstance(error, HTTPException):
            return (
                jsonify(
                    {
                        "error": error.name,
                        "message": error.description,
                    }
                ),
                error.code,
            )

        req_id = getattr(g, "request_id", "unknown")
        app.logger.error(
            f"Unhandled server exception: {str(error)}",
            exc_info=True,
            extra={
                "request_id": req_id,
                "error_type": error.__class__.__name__,
                "error_details": str(error),
            },
        )
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected server error occurred. Please consult application logs.",
                    "request_id": req_id,
                }
            ),
            500,
        )
