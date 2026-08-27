from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AccountState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class TenantOnboarding(BaseModel):
    tenant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class AccountChange(BaseModel):
    state: AccountState


class CampaignMessage(BaseModel):
    recipient_id: str = Field(min_length=1)
    to: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    body: str = Field(min_length=1, max_length=1600)


class CampaignRequest(BaseModel):
    campaign_id: str = Field(min_length=1)
    messages: list[CampaignMessage] = Field(min_length=1, max_length=100)


class MessageReceipt(BaseModel):
    recipient_id: str
    message_id: str


class CampaignReceipt(BaseModel):
    campaign_id: str
    accepted: list[MessageReceipt]


@dataclass
class Tenant:
    tenant_id: str
    display_name: str
    state: AccountState = AccountState.ACTIVE
    message_ids: dict[str, list[str]] = field(default_factory=dict)


class CampaignService:
    def __init__(self, sms: Any, status_reader: Any | None = None) -> None:
        self.sms = sms
        self.status_reader = status_reader or sms
        self.tenants: dict[str, Tenant] = {}

    def onboard(self, request: TenantOnboarding) -> Tenant:
        tenant = Tenant(tenant_id=request.tenant_id, display_name=request.display_name)
        self.tenants[tenant.tenant_id] = tenant
        return tenant

    def change_account(self, tenant_id: str, change: AccountChange) -> Tenant:
        tenant = self._tenant(tenant_id)
        tenant.state = change.state
        return tenant

    def send_campaign(self, tenant_id: str, request: CampaignRequest) -> CampaignReceipt:
        tenant = self._tenant(tenant_id)
        if tenant.state is not AccountState.ACTIVE:
            raise PermissionError(f"tenant account is {tenant.state.value}")
        if request.campaign_id in tenant.message_ids:
            raise ValueError("campaign_id has already been accepted for this tenant")

        receipts: list[MessageReceipt] = []
        for message in request.messages:
            result = self.sms.send(
                to=message.to,
                body=message.body,
                idempotency_key=f"{tenant_id}:{request.campaign_id}:{message.recipient_id}",
            )
            receipts.append(
                MessageReceipt(recipient_id=message.recipient_id, message_id=str(result["message_id"]))
            )
        tenant.message_ids[request.campaign_id] = [item.message_id for item in receipts]
        return CampaignReceipt(campaign_id=request.campaign_id, accepted=receipts)

    def campaign_status(self, tenant_id: str, campaign_id: str) -> list[dict[str, object]]:
        tenant = self._tenant(tenant_id)
        return [self.status_reader.status(message_id) for message_id in tenant.message_ids.get(campaign_id, [])]

    def _tenant(self, tenant_id: str) -> Tenant:
        try:
            return self.tenants[tenant_id]
        except KeyError as exc:
            raise LookupError("tenant not found") from exc
