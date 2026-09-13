# TenantTriage

A Telegram maintenance agent that asks the missing question, tracks one active case per tenant, escalates worsening issues, and keeps the tenant updated when their property manager acknowledges the report.

Built for a focused hackathon demo. Python 3.9+ and the standard library are the only runtime dependencies.

## Run locally

```sh
python3 app.py
```

Open http://127.0.0.1:8080. The default is **demo mode**: the classifier is a small deterministic simulation, and every outgoing action is labelled `simulated`. No API calls or external messages occur. Demo and live data use separate SQLite files.

### Rehearse the two-minute story

1. Select **Leaking sink**, then **Send message**. The agent asks whether the water is contained.
2. Select **Send worsening update**, then **Send message**. The existing case becomes high priority. Expand the manager notification and email in Action history.
3. Click **Acknowledge case** on the manager's desk. The tenant receives the acknowledgement.
4. Select **Check status**, then send. Show the saved state and notification status.
5. Close the case before rehearsing another issue.

To demonstrate recovery: arm **Simulate next email failure** before a fresh urgent report. The email appears as `failed`; click **Retry** to recover it. This is explicitly simulated, not evidence of live provider reliability.

## Connect real services

Copy `.env.example` to `.env` and fill it locally. Never commit credentials.

```sh
cp .env.example .env
```

Set `APP_MODE=live`, then configure:

| Setting | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Uses your OpenRouter credits; takes precedence over OpenAI when set |
| `OPENROUTER_MODEL` | Defaults to `openai/gpt-4o-mini`; select a model/provider supporting images and structured outputs |
| `OPENAI_API_KEY` | Alternative direct OpenAI provider |
| `TELEGRAM_BOT_TOKEN` | Create a bot through BotFather |
| `TENANT_CHAT_ID` | Numeric private-chat ID of the registered tenant |
| `MANAGER_CHAT_ID` | A different numeric private-chat ID for the property manager |
| `RESEND_API_KEY` | Email provider key |
| `RESEND_FROM` | Sender allowed by your Resend account/domain |
| `MANAGER_EMAIL` | Intended manager recipient |
| `TENANT_NAME`, `UNIT_ID`, `PROPERTY_NAME` | Your demonstration property |

Both people must start a private conversation with the bot before it can message them. Obtain the chat IDs from Telegram's `getUpdates` response during setup, before starting this app's polling worker. Only run one polling instance for a bot token. Remove any existing webhook before using polling.

Restart `python3 app.py` after configuring. The console becomes read-only. Tenants send reports and photos directly to Telegram, use `/status` to check progress, and `/help` for instructions. Managers acknowledge using the inline button and close cases with `/close TKT-XXXXXXXX`.

Starting live mode enables real delivery to those configured recipients. This implementation has not been verified against your accounts until a live rehearsal is performed. Provider acceptance (`sent`) is not proof of inbox delivery or human acknowledgement.

Exa is intentionally not used: tenant reports and a configured property SOP are the relevant sources for this MVP; public web search would not establish property-specific facts.

## Behavior and boundaries

- One registered tenant, one property, one manager, one active case per tenant. All follow-ups attach to that case until the manager closes it. Split unrelated issues manually; multi-property onboarding is outside this MVP.
- SOP v1 response targets: low/medium 48 hours, high 2 hours, crisis immediate attention. These are **response targets, not guaranteed repairs**. Set this policy to match the actual property before using it operationally.
- Priority can rise automatically but cannot fall until a human closes the case. Crisis reports prompt immediate human attention. The application never books a contractor or promises a resolution.
- Initial cases and meaningful changes create manager Telegram notifications. Urgent cases or human-review cases also queue email. Routine requests do not create email noise.
- Lease/legal inquiries are handed to the manager; no lease RAG or notice drafting is implemented.
- Photos are accepted in live Telegram and passed to a vision-capable model as image bytes. Telegram file IDs are retained in the case history; the console shows an attachment marker, not a photo preview. No bot-token URLs are logged. There is no browser photo upload in rehearsal mode.
- The LLM returns a validated assessment. Application code chooses recipients, priority policy, and side effects. It does not obey tool instructions from tenant text or images.
- Model failures persist the case for human review and create a visible assessment-failure record. Delivery failures remain in Action history and are never represented as successful sends.

## Persistence and retry guarantees

SQLite transactions save the ticket, messages, deduplication key, and outbox together before external delivery. Telegram update offsets persist across restarts. Replayed updates do not create new tickets or enqueue duplicate actions. Acknowledgement is idempotent.

Outgoing actions have `pending`, `sending`, `sent`/`simulated`, `failed`, or `uncertain` states. An interrupted in-flight send becomes `uncertain` after restart. Resend requests use the action UUID as their idempotency key. Telegram offers no equivalent send idempotency key: a timeout can occur after delivery. Check the recipient before retrying a failed or uncertain live action. Failed sends are not automatically retried in a loop. The demo console exposes retries; live retries use the local operator command below.

```sh
python3 manage.py retry ACTION_UUID
```

Stop the main app first when using operator commands. Check Action history for the action UUID (or `python3 manage.py actions`). An email accepted outside Resend's idempotency window may also duplicate on retry.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests cover follow-up escalation, duplicate updates, email recovery, manager authorization, repeat acknowledgement, crisis priority, model failure, ambiguous reports, close/reopen behavior, restart recovery, lease handoff, provider schema validation, and Telegram photo/callback routing. Provider HTTP calls in tests are mocked; they do not establish live classification accuracy or delivery reliability.

## Files

- `engine.py`: SQLite state machine, policy, conversation memory, transactional outbox.
- `adapters.py`: local classifier, OpenRouter/OpenAI assessment, Telegram and Resend delivery.
- `app.py`: loopback-only console server and Telegram long polling.
- `config.py`: environment loading and live configuration checks.
- `static/`: responsive tenant/manager rehearsal console.

The console binds only to loopback and checks Host plus an anti-CSRF token. It is a local operator interface, not a deployable public dashboard. There is no multi-user web authentication. Keep demo data synthetic; this MVP retains conversation text and file references locally with no automatic retention policy.

## API references

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Resend email API](https://resend.com/docs/api-reference/emails/send-email)
