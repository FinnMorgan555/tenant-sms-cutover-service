from fastapi import FastAPI, HTTPException

from .campaign_service import AccountChange, CampaignRequest, CampaignService, TenantOnboarding
from .infrai_sms import InfraiError, InfraiSmsClient
from .infrai_status import InfraiStatusClient

app = FastAPI(title="SaaS SMS campaign cutover")
service = CampaignService(InfraiSmsClient(), InfraiStatusClient())


@app.post("/tenants", status_code=201)
def onboard_tenant(request: TenantOnboarding) -> dict[str, str]:
    tenant = service.onboard(request)
    return {"tenant_id": tenant.tenant_id, "state": tenant.state.value}


@app.put("/tenants/{tenant_id}/account")
def change_account(tenant_id: str, request: AccountChange) -> dict[str, str]:
    try:
        tenant = service.change_account(tenant_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tenant_id": tenant.tenant_id, "state": tenant.state.value}


@app.post("/tenants/{tenant_id}/campaigns", status_code=202)
def send_campaign(tenant_id: str, request: CampaignRequest) -> dict[str, object]:
    try:
        return service.send_campaign(tenant_id, request).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail={"code": exc.code}) from exc


@app.get("/tenants/{tenant_id}/campaigns/{campaign_id}/status")
def campaign_status(tenant_id: str, campaign_id: str) -> list[dict[str, object]]:
    try:
        return service.campaign_status(tenant_id, campaign_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail={"code": exc.code}) from exc
