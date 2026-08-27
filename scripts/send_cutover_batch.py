import json
import os

from saas_sms_cutover.campaign_service import CampaignRequest, CampaignService, TenantOnboarding
from saas_sms_cutover.infrai_sms import InfraiSmsClient
from saas_sms_cutover.infrai_status import InfraiStatusClient


def main() -> None:
    destination = os.environ.get("DEMO_SMS_TO")
    if not destination:
        raise SystemExit("DEMO_SMS_TO is required")

    service = CampaignService(InfraiSmsClient(), InfraiStatusClient())
    service.onboard(TenantOnboarding(tenant_id="acme", display_name="Acme Operations"))
    request = CampaignRequest.model_validate(
        {
            "campaign_id": "cutover-smoke-001",
            "messages": [
                {
                    "recipient_id": "maintainer",
                    "to": destination,
                    "body": "Acme SMS cutover check: delivery path is active.",
                }
            ],
        }
    )
    receipt = service.send_campaign("acme", request)
    print(json.dumps(receipt.model_dump(), indent=2))
    print(json.dumps(service.campaign_status("acme", request.campaign_id), indent=2))


if __name__ == "__main__":
    main()
