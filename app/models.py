from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional
from app.database import get_db


class ValidationError(Exception):
    """Raised when client input data violates validation constraints."""
    pass


class DuplicateSkuError(Exception):
    """Raised when an inventory SKU already exists."""
    pass


class ProductNotFoundError(Exception):
    """Raised when requested product ID does not exist."""
    pass


def product_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row instance to a clean JSON-serializable dictionary."""
    return {
        "id": row["id"],
        "name": row["name"],
        "sku": row["sku"],
        "category": row["category"],
        "price": round(float(row["price"]), 2),
        "stock_quantity": int(row["stock_quantity"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def validate_product_payload(data: Any) -> Dict[str, Any]:
    """Validate incoming payload for product creation."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a valid JSON object.")

    required_fields = ["name", "sku", "category", "price", "stock_quantity"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    # Name validation
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 255:
        raise ValidationError("Field 'name' must be a non-empty string under 255 characters.")

    # SKU validation
    sku = str(data.get("sku", "")).strip().upper()
    if not sku or len(sku) > 100:
        raise ValidationError("Field 'sku' must be a non-empty alphanumeric string under 100 characters.")

    # Category validation
    category = str(data.get("category", "")).strip()
    if not category or len(category) > 100:
        raise ValidationError("Field 'category' must be a non-empty string under 100 characters.")

    # Price validation
    price_val = data.get("price")
    if not isinstance(price_val, (int, float)) or isinstance(price_val, bool):
        raise ValidationError("Field 'price' must be a numeric value.")
    if price_val <= 0:
        raise ValidationError("Field 'price' must be greater than zero.")
    price = round(float(price_val), 2)

    # Stock quantity validation
    stock_val = data.get("stock_quantity")
    if not isinstance(stock_val, int) or isinstance(stock_val, bool):
        raise ValidationError("Field 'stock_quantity' must be an integer.")
    if stock_val < 0:
        raise ValidationError("Field 'stock_quantity' cannot be negative.")

    return {
        "name": name,
        "sku": sku,
        "category": category,
        "price": price,
        "stock_quantity": stock_val,
    }


def validate_stock_payload(data: Any) -> int:
    """Validate incoming payload for stock quantity update."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a valid JSON object.")

    if "stock_quantity" not in data:
        raise ValidationError("Missing required field 'stock_quantity'.")

    stock_val = data.get("stock_quantity")
    if not isinstance(stock_val, int) or isinstance(stock_val, bool):
        raise ValidationError("Field 'stock_quantity' must be an integer.")
    if stock_val < 0:
        raise ValidationError("Field 'stock_quantity' cannot be negative.")

    return stock_val


class ProductRepository:
    """Data Access Object for inventory products stored in SQLite."""

    @staticmethod
    def list_products(
        category: Optional[str] = None,
        in_stock: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        db = get_db()
        query = "SELECT * FROM products WHERE 1=1"
        params: List[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category.strip())

        if in_stock is True:
            query += " AND stock_quantity > 0"
        elif in_stock is False:
            query += " AND stock_quantity = 0"

        query += " ORDER BY id ASC"
        cursor = db.execute(query, params)
        rows = cursor.fetchall()
        return [product_row_to_dict(r) for r in rows]

    @staticmethod
    def get_by_id(product_id: int) -> Dict[str, Any]:
        db = get_db()
        cursor = db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            raise ProductNotFoundError(f"Product with ID {product_id} does not exist.")
        return product_row_to_dict(row)

    @staticmethod
    def get_by_sku(sku: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        cursor = db.execute("SELECT * FROM products WHERE sku = ?", (sku.upper(),))
        row = cursor.fetchone()
        return product_row_to_dict(row) if row else None

    @staticmethod
    def create(payload: Dict[str, Any]) -> Dict[str, Any]:
        validated = validate_product_payload(payload)
        db = get_db()

        now = datetime.now(timezone.utc).isoformat()
        try:
            cursor = db.execute(
                """
                INSERT INTO products (name, sku, category, price, stock_quantity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validated["name"],
                    validated["sku"],
                    validated["category"],
                    validated["price"],
                    validated["stock_quantity"],
                    now,
                    now,
                ),
            )
            db.commit()
            new_id = cursor.lastrowid
            return ProductRepository.get_by_id(new_id)
        except sqlite3.IntegrityError as exc:
            db.rollback()
            if "UNIQUE constraint failed: products.sku" in str(exc) or "products.sku" in str(exc):
                raise DuplicateSkuError(f"Product with SKU '{validated['sku']}' already exists.")
            raise ValidationError(f"Database constraint violation: {exc}")

    @staticmethod
    def update_stock(product_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        new_quantity = validate_stock_payload(payload)
        db = get_db()

        # Check existence
        existing = ProductRepository.get_by_id(product_id)

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            UPDATE products
            SET stock_quantity = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_quantity, now, product_id),
        )
        db.commit()
        return ProductRepository.get_by_id(product_id)
