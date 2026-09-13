# Report and repair workflow

Tenant commands:

- `/new` or `/new description`: start a separate report while keeping existing reports.
- `/cases`: list reports and their IDs.
- `/case TKT-ID`: select a report for follow-up messages.
- `/status`: view the selected report.
- `/resolved TKT-ID`: confirm a completed repair and close the report.
- `/unresolved TKT-ID`: return a completed repair to in-progress work.

Routine intake collects the affected area and symptoms, onset, impact, and attempted fixes/access availability over multiple messages. Manager submission waits until these answers are collected. Unknown details can be stated explicitly. High-priority reports and human-review cases bypass routine intake.

Managers can acknowledge via Telegram buttons, then use `/assign TKT-ID technician`, `/progress TKT-ID details`, and `/complete TKT-ID details`. These actions are also available in the dashboard's Repair update form. Completion requests tenant confirmation; it does not close the ticket. `/close TKT-ID` also requests confirmation.

While the live app runs, reminders are checked every minute. Unacknowledged cases receive their first reminder at the response deadline. Acknowledgement and repair updates set a 24-hour follow-up. Subsequent reminders repeat every 24 hours, or every two hours for high/crisis cases. Tenants receive progress reminders; completed repairs receive confirmation reminders. Closed cases and incomplete intake do not receive reminders. Reminder deadlines persist across restarts. Delivery failures remain visible in the outbox for manager retry.

Assignment records the technician and informs the tenant. Actual contractor dispatch and external calendar synchronization remain manual; inspection slots use the existing local calendar.

Restart the live app to load code changes. The static public demo has a separate simulated backend and does not run this Python workflow.
