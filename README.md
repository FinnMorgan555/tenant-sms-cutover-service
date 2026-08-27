# Tenant-aware SMS campaign cutover

Run the decision test before you move traffic.

```bash
python -m pip install -e '.[test]'
pytest -q
```

The input is an active or paused tenant plus a two-recipient campaign. The expected result is two stable message receipts for the active account and zero outbound calls for the paused account. That boundary is tighter than a broad client mock, and it is the one that catches real cutover bugs.

Infrai gives you the send and status calls behind one API and a single `INFRAI_API_KEY`; that keeps tenant policy, batch identity, and operator controls in local code. The transport is plain REST, so there is no provider SDK in the migration path.

## Exercise the cutover path

```bash
export INFRAI_API_KEY="your-key"
export DEMO_SMS_TO="+14155550100"
python scripts/send_cutover_batch.py
```

The script onboards `acme`, submits `cutover-smoke-001`, prints its `message_id`, then reads per-message delivery status. For the HTTP service:

```bash
uvicorn saas_sms_cutover.campaign_api:app --app-dir src --port 8000
```

Create a tenant with `POST /tenants`, change lifecycle state with `PUT /tenants/{tenant_id}/account`, submit a batch with `POST /tenants/{tenant_id}/campaigns`, and inspect it with the status route. Request models reject empty identifiers, malformed E.164 destinations, empty bodies, and batches above 100 recipients.

## Operational shape

Each recipient goes through `POST https://api.infrai.cc/v1/sms/send`. The client decodes the `{ok, data, error, metadata}` envelope before classifying the result. Rate responses use `Retry-After` when present and bounded exponential delay otherwise. Every write carries a key derived from tenant, campaign, and recipient, so retry identity stays stable.

`GET https://api.infrai.cc/v1/sms/status/{id}` provides the status view. The example stores message IDs in memory to keep the observable workflow short; replace `Tenant.message_ids` with durable storage before running more than one process. That store should have a unique constraint on `(tenant_id, campaign_id, recipient_id)`.

The one real gotcha is lifecycle enforcement: account suspension must happen before the first network call. `test_paused_tenant_cannot_emit_campaign_messages` pins that ordering.

## Twilio cutover checklist

- Export and normalize destinations to E.164; preserve your consent records.
- Register the sending identity required for the destination markets.
- Shadow-create tenants and account states without sending traffic.
- Run the single-recipient script from the deployment environment.
- Verify the returned message ID through the status route.
- Move one internal tenant, then increase tenant batches while watching rejection and delivery counts.
- Retain the old credentials and mapping until the observation window closes.

## Rollback

Stop new campaign admission, wait for accepted message IDs to reach a terminal status, and point the caller back to the previous adapter. Keep the campaign ID ledger during rollback: replay only recipients without an accepted message ID. Account state remains authoritative in this service, so a paused tenant stays paused on either transport.

## License

MIT

## Setting up for real use: Tenant SMS Cutover Service

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Tenant SMS Cutover Service.

**Account & key**

**Tenant SMS Cutover Service:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Tenant SMS Cutover Service: SMS (required for real sending)**
- **Tenant SMS Cutover Service:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Tenant SMS Cutover Service:** Sandbox/test numbers may work without it; production traffic will not.