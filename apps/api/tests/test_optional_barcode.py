"""D-112: a product may be created without a barcode and still be used everywhere."""

from __future__ import annotations

from test_invoice_editor import _auth, _catalog, _owner_context


def test_product_without_barcode_is_found_by_name_and_invoiced(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "nobarcode")
    category, _product, customer = _catalog(client, tenant, token)
    for blank in (None, "", "   "):
        payload = {
            "category_id": category["id"],
            "name": f"Loose Zaatar {blank!r}",
            "unit_price": "3.5000",
            "currency": "USD",
            "price_basis": "PIECE",
            "is_published": True,
        }
        if blank is not None:
            payload["barcode"] = blank
        created = client.post(
            f"/api/v1/tenants/{tenant}/products", headers=_auth(token), json=payload
        )
        assert created.status_code == 201, created.text
        assert created.json()["barcode"] is None and created.json()["barcodes"] == []
    product = created.json()

    listed = client.get(f"/api/v1/tenants/{tenant}/products", headers=_auth(token)).json()
    assert sum(1 for row in listed["products"] if row["barcode"] is None) == 3

    found = client.get(
        "/api/v1/invoices/catalog-search",
        params={"tenant_id": tenant, "query": "Loose Zaatar"},
        headers=_auth(token),
    ).json()["matches"]
    match = next(row for row in found if row["product_id"] == product["id"])
    assert match["barcode"] is None and match["package_level"] == "PIECE"

    draft = client.post(
        "/api/v1/invoices",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={
            "client_command_id": "7b0c5a8e-1111-4a2b-9c3d-000000000112",
            "customer_id": customer["id"],
            "currency": "USD",
            "items": [
                {"product_id": product["id"], "quantity_expression": "2", "price_basis": "PIECE"}
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["items"][0]["barcode"] is None

    # A barcode can be added later, and it is still unique within the business.
    added = client.post(
        f"/api/v1/tenants/{tenant}/products/{product['id']}/barcodes",
        headers=_auth(token),
        json={"barcode": "2900000001120", "package_level": "PIECE"},
    )
    assert added.status_code in {200, 201}, added.text
    assert added.json()["barcode"] == "2900000001120"
    duplicate = client.post(
        f"/api/v1/tenants/{tenant}/products",
        headers=_auth(token),
        json={
            "category_id": category["id"],
            "name": "Copy",
            "barcode": "2900000001120",
            "unit_price": "1",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    assert duplicate.status_code == 409
