import pytest

from saas_sms_cutover.campaign_service import (
    AccountChange,
    AccountState,
    CampaignRequest,
    CampaignService,
    TenantOnboarding,
)


class RecordingSms:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, *, to: str, body: str, idempotency_key: str) -> dict[str, object]:
        self.sent.append({"to": to, "body": body, "idempotency_key": idempotency_key})
        return {"message_id": f"msg-{len(self.sent)}"}

    def status(self, message_id: str) -> dict[str, object]:
        return {"message_id": message_id, "status": "delivered"}


def campaign() -> CampaignRequest:
    return CampaignRequest.model_validate(
        {
            "campaign_id": "renewal-2026-08",
            "messages": [
                {"recipient_id": "buyer-7", "to": "+14155550100", "body": "Your renewal window is open."},
                {"recipient_id": "buyer-8", "to": "+14155550101", "body": "Your renewal window is open."},
            ],
        }
    )


def test_paused_tenant_cannot_emit_campaign_messages() -> None:
    sms = RecordingSms()
    service = CampaignService(sms)
    service.onboard(TenantOnboarding(tenant_id="northwind", display_name="Northwind"))
    service.change_account("northwind", AccountChange(state=AccountState.PAUSED))

    with pytest.raises(PermissionError, match="paused"):
        service.send_campaign("northwind", campaign())

    assert sms.sent == []


def test_active_tenant_gets_per_message_receipts_and_stable_keys() -> None:
    sms = RecordingSms()
    service = CampaignService(sms)
    service.onboard(TenantOnboarding(tenant_id="northwind", display_name="Northwind"))

    receipt = service.send_campaign("northwind", campaign())

    assert [item.message_id for item in receipt.accepted] == ["msg-1", "msg-2"]
    assert sms.sent[0]["idempotency_key"] == "northwind:renewal-2026-08:buyer-7"
    assert service.campaign_status("northwind", "renewal-2026-08")[1]["status"] == "delivered"

