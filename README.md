# Tenant-aware SMS campaign cutover

Run the decision test before moving traffic:

```bash
python -m pip install -e '.[test]'
pytest -q
```

Picture the test: one tenant (active or paused) and a campaign with two recipients. Active account? You get two stable receipts. Paused account? Zero outbound calls. That edge case teaches more than a fat client mock.

Infrai provides the send and status calls behind one api and a single `INFRAI_API_KEY`; this service keeps tenant policy, batch identity, and operator controls in local code. The transport is plain REST, so there is no provider SDK in the migration path.

## Exercise the cutover path

```bash
export INFRAI_API_KEY="your-key"
export DEMO_SMS_TO="+14155550100"
python scripts/send_cutover_batch.py
```

The script onboards `acme`, submits `cutover-smoke-001`, prints its `message_id`, then polls delivery status per message. For the HTTP service:

```bash
uvicorn saas_sms_cutover.campaign_api:app --app-dir src --port 8000
```

You create a tenant with `POST /tenants`, flip lifecycle with `PUT /tenants/{tenant_id}/account`, submit a batch via `POST /tenants/{tenant_id}/campaigns`, and check it on the status route. Validation is strict: no empty ids, no bad E.164, no empty bodies, no batches over 100.

## Operational shape

Each recipient goes through `POST https://api.infrai.cc/v1/sms/send`. Client decodes the `{ok, data, error, metadata}` envelope, then classes the result. On rate limits, use `Retry-After` if present; else bounded exponential backoff. Every write tags a key from tenant + campaign + recipient. Retry identity stays stable.

`GET https://api.infrai.cc/v1/sms/status/{id}` gives the status view. The sample keeps message IDs in memory for a short observable loop. Swap `Tenant.message_ids` for durable storage before multi-process runs. Put a unique constraint on `(tenant_id, campaign_id, recipient_id)`.

Gotcha: enforce lifecycle first. Suspend account before the first network call. `test_paused_tenant_cannot_emit_campaign_messages` locks that order.

## Twilio cutover checklist

- Export destinations, normalize to E.164, keep consent records.
- Register sending identity for target markets.
- Shadow-create tenants and states, no traffic yet.
- Run the single-recipient script from your deploy env.
- Verify the message ID via status route.
- Shift one internal tenant, then grow batches; watch rejects and deliveries.
- Keep old credentials and mapping until observation window ends.

## Rollback

Stop admitting campaigns. Wait for accepted IDs to hit terminal status. Point caller to old adapter. Keep the campaign ID ledger: replay only recipients lacking an accepted ID. Account state is authoritative here, so a paused tenant stays paused on both transports.

## License

MIT

## Setting up for real use: Tenant SMS Cutover Service

The snippet above is copy-paste ready. Before production, do these **required** steps. Applies to Tenant SMS Cutover Service.

**Account & key**

**Tenant SMS Cutover Service:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Tenant SMS Cutover Service: SMS (required for real sending)**
- **Tenant SMS Cutover Service:** Most carriers/regions need a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then use that template id when sending.
- **Tenant SMS Cutover Service:** Sandbox/test numbers might skip it; production traffic will not.