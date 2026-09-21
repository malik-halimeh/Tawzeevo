"""Phase 8 P8-M3: tenant branding is presentation only and tenant-isolated; storefront and
invoice pages render it; public aggregates keep Phase 1 stats, expose nothing sensitive and
withhold values on small cohorts (PHASE_08.md F/G/J; D-070)."""

from __future__ import annotations

import io
import re

from PIL import Image
from test_delivery_tasks import _driver, _post
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice
from test_storefront import _publish, _slug

PNG_MAGIC = bytes([137]) + b"PNG" + bytes([13, 10, 26, 10])


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 32), (200, 40, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_branding_is_owner_only_isolated_and_rendered_on_public_pages(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p8brand")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    path = f"/api/v1/tenants/{tenant}/branding"

    # Money before any branding exists: a confirmed invoice and the public price. Branding is
    # presentation only (PHASE_08.md F/G, D-070); these values must be identical afterwards.
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    money_before = {
        key: confirmed[key]
        for key in ("net_sales", "subtotal", "discount_total", "total_due", "current_revision_id")
        if key in confirmed
    }
    assert money_before["net_sales"] and money_before["current_revision_id"]
    price_before = client.get(f"/api/v1/public/{slug}/catalog/products").json()["items"][0]["price"]

    # Defaults before anything is saved.
    initial = client.get(path, headers=_auth(token))
    assert initial.status_code == 200, initial.text
    assert initial.json()["default_language"] == "en" and initial.json()["version"] == 0
    assert initial.json()["has_logo"] is False

    # Save identity, theme, texts, invoice presentation and localization.
    saved = client.put(
        path,
        headers=_auth(token),
        json={
            "description": "Fresh water to your door",
            "phone": "03 111 222",
            "whatsapp": "70 333 444",
            "email": "hello@cedar.example",
            "primary_color": "#1f6f5f",
            "secondary_color": "#f2c14e",
            "storefront_title": "Cedar Van",
            "banner_text": "Free delivery in Beirut this week",
            "social_links": {"instagram": "https://instagram.com/cedar", "x": ""},
            "about_text": "Family business since 2001",
            "invoice_header": "Cedar Van · Beirut",
            "invoice_footer": "Thank you for your trust",
            "invoice_terms": "Payment within 7 days",
            "thank_you_text": "See you next week",
            "invoice_qr_enabled": True,
            "default_language": "ar",
            "date_format": "YYYY-MM-DD",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["phone"] == "+9613111222" and body["whatsapp"] == "+96170333444"
    assert body["social_links"] == {"instagram": "https://instagram.com/cedar"}  # blank dropped
    assert body["version"] == 1 and body["default_language"] == "ar"
    bad_color = client.put(path, headers=_auth(token), json={"primary_color": "red"})
    assert bad_color.status_code == 422
    bad_link = client.put(
        path, headers=_auth(token), json={"social_links": {"instagram": "http://x"}}
    )
    assert bad_link.status_code == 422
    stale = client.put(path, headers=_auth(token), json={"banner_text": "x", "expected_version": 1})
    assert stale.status_code == 200 and stale.json()["version"] == 2
    conflict = client.put(
        path, headers=_auth(token), json={"banner_text": "y", "expected_version": 1}
    )
    assert conflict.status_code == 409

    # Logo: validated like a product image, served publicly with cache headers.
    logo = client.post(
        f"{path}/logo",
        headers=_auth(token),
        files={"file": ("logo.png", _png(), "image/png")},
    )
    assert logo.status_code == 200, logo.text
    assert logo.json()["has_logo"] is True and logo.json()["logo_path"].startswith(
        f"/api/v1/public/{slug}/branding/logo"
    )
    served = client.get(logo.json()["logo_path"])
    assert served.status_code == 200 and served.headers["content-type"].startswith("image/")
    assert "max-age" in served.headers["cache-control"]
    not_image = client.post(
        f"{path}/logo", headers=_auth(token), files={"file": ("x.txt", b"hello", "text/plain")}
    )
    assert not_image.status_code == 415

    # Storefront renders the public block; nothing owner-only leaks (no invoice terms, no timezone).
    shop = client.get(f"/api/v1/public/{slug}/catalog")
    assert shop.status_code == 200, shop.text
    branding = shop.json()["branding"]
    assert branding["storefront_title"] == "Cedar Van" and branding["primary_color"] == "#1f6f5f"
    assert branding["banner_text"] == "x" and branding["default_language"] == "ar"
    assert branding["logo_path"] == logo.json()["logo_path"]
    assert "invoice_terms" not in branding and "timezone" not in branding

    # Branding cannot change prices or money: the public price and the confirmed invoice are
    # byte-for-byte what they were before any branding was saved (no new revision either).
    listed = client.get(f"/api/v1/public/{slug}/catalog/products").json()["items"][0]
    assert listed["price"] == price_before == product["unit_price"]
    after = client.get(
        f"/api/v1/invoices/{confirmed['id']}?tenant_id={tenant}", headers=_auth(token)
    )
    assert after.status_code == 200, after.text
    assert {key: after.json()[key] for key in money_before} == money_before

    # The customer invoice page carries the invoice presentation block.
    link = _post(client, tenant, token, f"/api/v1/invoices/{confirmed['id']}/capabilities", {})
    assert link.status_code == 201, link.text
    secret = link.json()["public_path"].split("#", 1)[1]
    page = client.get("/api/v1/public/invoice/data", headers={"X-Invoice-Capability": secret})
    assert page.status_code == 200, page.text
    inv = page.json()["branding"]
    assert (
        inv["invoice_header"] == "Cedar Van · Beirut"
        and inv["thank_you_text"] == "See you next week"
    )
    assert inv["invoice_qr_enabled"] is True and inv["date_format"] == "YYYY-MM-DD"
    assert not re.search(r"privacy_text|social_links|primary_color", page.text)
    # Safe QR: PNG of the capability page only, only with the header, only when enabled.
    qr_path = "/api/v1/public/invoice/qr"
    qr = client.get(qr_path, headers={"X-Invoice-Capability": secret})
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png"
    assert qr.headers["cache-control"] == "no-store" and qr.content.startswith(PNG_MAGIC)
    assert client.get(qr_path).status_code == 404
    client.put(path, headers=_auth(token), json={"invoice_qr_enabled": False})
    assert client.get(qr_path, headers={"X-Invoice-Capability": secret}).status_code == 404
    html = client.get("/api/v1/public/invoice")
    assert "img-src 'self' blob:" in html.headers["content-security-policy"]
    assert 'id="qr"' in html.text and 'id="brand-header"' in html.text

    # Isolation: drivers and other businesses cannot read or write it.
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-p8brand@example.com")
    assert client.get(path, headers=_auth(driver_token)).status_code == 403
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p8brand2")
    assert client.get(path, headers=_auth(other_token)).status_code == 403
    theirs = client.get(
        f"/api/v1/tenants/{other_tenant}/branding", headers=_auth(other_token)
    ).json()
    assert theirs["storefront_title"] is None and theirs["has_logo"] is False


def test_public_stats_keep_phase1_and_withhold_small_cohorts(client, session_factory):
    # Phase 1 mandatory stats remain exactly as before.
    assert set(client.get("/stats/count").json()) == {"count"}
    assert set(client.get("/stats/average-age").json()) == {"average_age"}
    assert isinstance(client.get("/stats/top-cities").json(), list)
    # A tiny platform withholds every aggregate value and says why (D-070).
    stats = client.get("/stats/platform")
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["sufficient_data"] is False
    assert body["minimum_businesses"] == 5 and body["minimum_customers"] == 20
    assert body["active_businesses"] is None and body["confirmed_invoices_last_30_days"] is None
    # Nothing sensitive is even a field.
    assert not re.search(
        r"revenue|sales|debt|outstanding|cost|price|profit|tenant_id|customer_name",
        stats.text,
        re.I,
    )
    _owner_context(client, session_factory, "p8stats-x")
    assert client.get("/stats/platform").json()["sufficient_data"] is False
