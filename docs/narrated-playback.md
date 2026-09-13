# Narrated dashboard playback

Open http://127.0.0.1:8097/?narration=1 on the normal dummy dashboard.

Start CleanShot with system audio capture, then click **Play narrated walkthrough**. The supplied San Francisco Coffee.m4a narration drives the screen changes. Space pauses/resumes and Escape stops. Playback ends after approximately 119.96 seconds and restores the actual saved dashboard state.

This is a visual replay using the existing fictional cases. The pending-to-booked transition is illustrative and does not mutate SQLite, send a notification, or reserve another appointment. The underlying cases may already be booked from previous takes. The simulation notice remains visible on the dashboard.

| Audio time | Screen |
| --- | --- |
| 0.00 | Dashboard introduction |
| 6.86 | Leak photo and tenant report |
| 21.28 | Containment question |
| 30.94 | Electrical risk and access context |
| 33.64 | Case header |
| 37.42 | Summary, priority, response target |
| 41.40 | Internal notes and next steps |
| 44.50 | Notification status |
| 47.54 | Worsening update and high priority |
| 57.28 | Tenant status question |
| 63.10 | AC intake |
| 67.50 | Slot offer and selection |
| 72.26 | Awaiting manager approval |
| 78.20 | Local reservation recorded |
| 80.92 | Dashboard during team credits |
| 92.76 | Coordination overview |
| 104.64 | Dashboard during future-scope narration |
| 114.96 | Dashboard closing |

Local speech recognition supplied section timestamps; the written script was used to interpret names and misrecognized terms. The original narration audio is unchanged. The raw transcript is in data/narration-timestamps.json.
