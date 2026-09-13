# UnitCue: two-minute recording cues

Use the isolated recording workspace, not the old dashboard server or public static demo. It runs the real Python workflow with simulated AI assessment and notifications. Two reports and their actual engine-generated intake transcripts are prepared; the leak is routine and the AC slots are not booked.

For a fresh take, run `python3 recording_demo.py --port 8099` on an unused port. Each launch creates a separate recording database and fresh future slots. It never resets existing cases or sends Telegram messages. Stop that recording server before reusing its port.

| Time | Screen and action |
| --- | --- |
| 0:00-0:08 | Dashboard home: UnitCue name and two active cases. |
| 0:08-0:20 | Open Plumbing. Show the first tenant message in Conversation: "My bathroom sink is leaking". |
| 0:20-0:38 | Scroll slowly through the saved intake: location/containment, start time, nearby electrics, attempted fixes/access. |
| 0:38-0:55 | Return to the case header. Show summary, medium priority, response target, next step, and simulated manager notification. |
| 0:55-1:12 | Click Send tenant follow-up, Worsening leak, then Send report. The same case reopens with crisis priority and manager Telegram/email notification records. |
| 1:12-1:32 | Close the case dialog. Select the Air conditioning case button in Rehearsal. Send `/status` to open its saved conversation and show room/details/slot offers. Click Send tenant follow-up, enter `1`, and Send report. Show awaiting approval. |
| 1:32-1:42 | In Inspection, click Approve reservation, then Confirm. Show booked and the tenant confirmation message. |
| 1:42-1:52 | Briefly show the recording server terminal alongside the dashboard. Avoid opening `.env` or the manager access key. |
| 1:52-2:00 | Close the dialog and click Dashboard. End with the escalated leak and upcoming AC appointment visible. |

## Narration adjustments

- Use the script's saved-conversation option. Say "Here is a saved tenant conversation from our simulated demo" before showing it. Do not imply this recording proves live Telegram delivery or model/photo understanding.
- The unit is already registered as B-12-03, so the bot does not ask which unit. Show the actual questions instead.
- The photo step is optional; omit it for this recording. Live Telegram accepts photos, but that integration is not exercised by this rehearsal.
- Say "local inspection reservation" for booking. A real contractor and external calendar are not connected.
- Say "keeps follow-ups connected to the same case". Separate issues can use `/new`; there can be more than one active report.

The technical stack statement is supported by the implementation: Python, SQLite, Telegram Bot API, browser dashboard, and structured OpenRouter/OpenAI assessment. Live provider health is a separate check.

## Verified

Automated rehearsal checks the exact worsening sentence, same-case escalation, AC isolation, pending selection without reservation, manager approval, and the final reservation. A browser rehearsal additionally exercised these visible controls. The routine intake cannot be bypassed with `/slots`.
