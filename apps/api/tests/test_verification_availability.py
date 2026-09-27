"""D-099: the verified-phone policy is offered only while a one-time code can be delivered."""

from __future__ import annotations

from test_invoice_editor import _auth, _owner_context

from tawzeevo_api.config import get_settings


def test_settings_offer_verified_only_with_a_usable_provider(client, session_factory, monkeypatch):
    _owner, tenant, token = _owner_context(client, session_factory, "vavail")

    # Development adapter outside production: codes can be delivered, VERIFIED is offered.
    usable = client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(token)).json()
    assert usable["verification_available"] is True
    assert usable["available_policies"] == ["LINK", "VERIFIED"]

    # A channel without an implemented adapter: not offered, and refused on save.
    monkeypatch.setattr(get_settings(), "customer_otp_provider", "unconfigured")
    settings = client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(token)).json()
    assert settings["verification_available"] is False
    assert settings["available_policies"] == ["LINK"]
    refused = client.put(
        f"/api/v1/tenants/{tenant}/storefront/access-policy",
        headers=_auth(token),
        json={"policy": "VERIFIED"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "OTP_PROVIDER_NOT_CONFIGURED"

    # It reappears by itself once a provider can deliver again.
    monkeypatch.setattr(get_settings(), "customer_otp_provider", "dev")
    again = client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(token)).json()
    assert again["available_policies"] == ["LINK", "VERIFIED"]
