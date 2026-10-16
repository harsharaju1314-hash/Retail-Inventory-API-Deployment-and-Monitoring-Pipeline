import json


def test_list_products_initially_empty(client):
    """GET /products should return an empty list when no inventory exists."""
    response = client.get("/products")
    assert response.status_code == 200
    data = response.get_json()
    assert data["products"] == []
    assert data["count"] == 0


def test_create_product_success(client):
    """POST /products with valid payload should create a product and return 201."""
    payload = {
        "name": "Barcode Scanner",
        "sku": "SCAN-WLS-001",
        "category": "Electronics",
        "price": 89.99,
        "stock_quantity": 25,
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 201

    data = response.get_json()
    assert "product" in data
    prod = data["product"]
    assert prod["id"] == 1
    assert prod["name"] == "Barcode Scanner"
    assert prod["sku"] == "SCAN-WLS-001"
    assert prod["category"] == "Electronics"
    assert prod["price"] == 89.99
    assert prod["stock_quantity"] == 25
    assert "created_at" in prod
    assert "updated_at" in prod


def test_create_product_missing_fields(client):
    """POST /products with missing fields must return 400 Bad Request."""
    incomplete_payload = {
        "name": "Receipt Paper",
        # Missing sku, category, price, stock_quantity
    }
    response = client.post("/products", json=incomplete_payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Bad Request"
    assert "Missing required fields" in data["message"]


def test_create_product_invalid_price(client):
    """POST /products with price <= 0 or non-numeric must return 400."""
    payload_zero_price = {
        "name": "Test Item",
        "sku": "TEST-001",
        "category": "General",
        "price": 0.00,
        "stock_quantity": 10,
    }
    response = client.post("/products", json=payload_zero_price)
    assert response.status_code == 400
    assert "greater than zero" in response.get_json()["message"]

    payload_negative_price = {
        "name": "Test Item",
        "sku": "TEST-002",
        "category": "General",
        "price": -15.50,
        "stock_quantity": 10,
    }
    response = client.post("/products", json=payload_negative_price)
    assert response.status_code == 400
    assert "greater than zero" in response.get_json()["message"]


def test_create_product_negative_stock(client):
    """POST /products with stock < 0 must return 400."""
    payload = {
        "name": "Test Item",
        "sku": "TEST-003",
        "category": "General",
        "price": 10.00,
        "stock_quantity": -5,
    }
    response = client.post("/products", json=payload)
    assert response.status_code == 400
    assert "cannot be negative" in response.get_json()["message"]


def test_create_product_duplicate_sku(client):
    """POST /products with duplicate SKU must return 409 Conflict."""
    payload = {
        "name": "Label Printer",
        "sku": "PRN-LBL-001",
        "category": "Electronics",
        "price": 199.50,
        "stock_quantity": 12,
    }
    res1 = client.post("/products", json=payload)
    assert res1.status_code == 201

    # Attempt to insert same SKU again
    res2 = client.post("/products", json=payload)
    assert res2.status_code == 409
    data = res2.get_json()
    assert data["error"] == "Conflict"
    assert "already exists" in data["message"]


def test_get_product_by_id_success(client):
    """GET /products/<id> returns product details when ID exists."""
    payload = {
        "name": "Cash Drawer",
        "sku": "DRW-CSH-001",
        "category": "Point of Sale",
        "price": 120.00,
        "stock_quantity": 8,
    }
    create_res = client.post("/products", json=payload)
    prod_id = create_res.get_json()["product"]["id"]

    get_res = client.get(f"/products/{prod_id}")
    assert get_res.status_code == 200
    assert get_res.get_json()["product"]["sku"] == "DRW-CSH-001"


def test_get_product_by_id_not_found(client):
    """GET /products/<id> returns 404 when product ID does not exist."""
    response = client.get("/products/99999")
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "Not Found"
    assert "does not exist" in data["message"]


def test_update_stock_success(client):
    """PATCH /products/<id>/stock successfully updates quantity."""
    payload = {
        "name": "Thermal Paper Roll",
        "sku": "PPR-THM-050",
        "category": "Supplies",
        "price": 2.50,
        "stock_quantity": 100,
    }
    create_res = client.post("/products", json=payload)
    prod_id = create_res.get_json()["product"]["id"]

    patch_res = client.patch(f"/products/{prod_id}/stock", json={"stock_quantity": 75})
    assert patch_res.status_code == 200
    updated_prod = patch_res.get_json()["product"]
    assert updated_prod["stock_quantity"] == 75


def test_update_stock_negative(client):
    """PATCH /products/<id>/stock rejects negative stock values."""
    payload = {
        "name": "Thermal Paper Roll",
        "sku": "PPR-THM-051",
        "category": "Supplies",
        "price": 2.50,
        "stock_quantity": 10,
    }
    create_res = client.post("/products", json=payload)
    prod_id = create_res.get_json()["product"]["id"]

    patch_res = client.patch(f"/products/{prod_id}/stock", json={"stock_quantity": -1})
    assert patch_res.status_code == 400
    assert "cannot be negative" in patch_res.get_json()["message"]


def test_update_stock_not_found(client):
    """PATCH /products/<id>/stock returns 404 if product does not exist."""
    patch_res = client.patch("/products/99999/stock", json={"stock_quantity": 10})
    assert patch_res.status_code == 404


def test_update_stock_missing_body(client):
    """PATCH /products/<id>/stock returns 400 on empty or invalid payload."""
    response = client.patch("/products/1/stock", data="plain text", content_type="text/plain")
    assert response.status_code == 400
    assert "Content-Type must be 'application/json'" in response.get_json()["message"]


def test_list_products_filtering(client):
    """GET /products supports category and stock availability filters."""
    client.post("/products", json={"name": "Item A", "sku": "ITM-A", "category": "Electronics", "price": 10.0, "stock_quantity": 5})
    client.post("/products", json={"name": "Item B", "sku": "ITM-B", "category": "Electronics", "price": 20.0, "stock_quantity": 0})
    client.post("/products", json={"name": "Item C", "sku": "ITM-C", "category": "Office", "price": 5.0, "stock_quantity": 15})

    # Filter by category
    res_cat = client.get("/products?category=Office")
    assert res_cat.status_code == 200
    assert res_cat.get_json()["count"] == 1
    assert res_cat.get_json()["products"][0]["sku"] == "ITM-C"

    # Filter by in_stock=true
    res_in_stock = client.get("/products?in_stock=true")
    assert res_in_stock.status_code == 200
    assert res_in_stock.get_json()["count"] == 2

    # Filter by in_stock=false
    res_out_of_stock = client.get("/products?in_stock=false")
    assert res_out_of_stock.status_code == 200
    assert res_out_of_stock.get_json()["count"] == 1
    assert res_out_of_stock.get_json()["products"][0]["sku"] == "ITM-B"
