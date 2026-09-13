# TenantTriage Design Guide

## Brand foundation

**TenantTriage** turns an uncertain maintenance report into a clear, visible next step. The brand should feel calm under pressure: practical enough for a property manager, reassuring enough for a tenant, and never theatrical about an urgent issue.

| Element | Direction |
| --- | --- |
| Brand promise | Every report has a clear next step. |
| Personality | Calm, capable, direct, accountable, human. |
| Voice | Plain language, short sentences, specific action and timing. |
| Avoid | Jargon, blame, false certainty, alarmist wording, playful treatment of emergencies. |
| Primary audience | Tenants reporting an issue and property managers coordinating a response. |

### Naming and tagline

Use **TenantTriage** as one word with a capital T in both parts. Prefer the tagline **“Every report. A clear next step.”** Use “Maintenance desk” only as a functional descriptor, not a replacement for the product name.

### Writing guidance

- Lead with status and action: “Your report is with the property manager.”
- State response targets as targets, never promises: “Target response: within 2 hours.”
- Make urgency factual: “Water is spreading” rather than “This is terrible.”
- Say when a person is involved: “The property manager has acknowledged your case.”
- In a crisis, put the immediate safety instruction first and hand off to a human.

## Visual direction

The UI is a **calm operational desk**, not a consumer chat app. It should use generous white space, crisp panel boundaries, data-forward hierarchy, and a restrained blue palette. Urgency colours communicate state only; they are not decoration.

### Logo and mark

The current tiled `▥` mark works as a compact signal of a building plan and an organized queue.

- Use the mark in a rounded blue tile when space is limited.
- Keep at least one mark-width of clear space around the logo.
- Do not recolour it for urgency, stretch it, add shadows, or use the mark alone where product recognition is still being established.

### Colour tokens

These tokens preserve the current interface and give semantic colours a clear purpose.

| Token | Hex | Use |
| --- | --- | --- |
| `--ink` | `#18314F` | Headings, primary text, logo wordmark |
| `--blue` | `#2458C7` | Primary actions, links, active signal |
| `--blue-dark` | `#1C469D` | Hover and pressed primary actions |
| `--sky` | `#EDF3FC` | Informational badges and soft surfaces |
| `--paper` | `#F6F9FD` | Page background and code/action detail surfaces |
| `--line` | `#D8E2EF` | Borders and dividers |
| `--muted` | `#60758D` | Supporting text only |
| `--success` | `#28664C` | Acknowledged, sent, recorded states |
| `--success-bg` | `#E5F3EC` | Success state background |
| `--amber` | `#975509` | High priority and response-at-risk states |
| `--amber-bg` | `#FFF0D9` | High-priority background |
| `--red` | `#AD2936` | Crisis, failed, and uncertain delivery states |
| `--red-bg` | `#FDE7E9` | Critical-state background |

Never depend on colour alone: pair priority with text (for example, “High priority”) and, where space permits, an icon or border treatment. Keep red reserved for true risk, failure, and crisis.

### Typography

Use the current system-forward stack for dependable local deployment:

```css
font-family: "Avenir Next", Avenir, "Segoe UI", sans-serif;
```

- Page title: 32–48px, weight 650, tight tracking (`-0.04em`).
- Panel and section titles: 17–21px, weight 650.
- Body: 14px with 1.5–1.6 line height.
- Metadata and labels: 11–12px with clear contrast; never use them for essential instructions alone.
- Ticket IDs and timestamps may use the same font at 11px; do not introduce a monospace face unless the application gains technical operator workflows.

### Spacing, shape, and elevation

- Base spacing unit: 4px. Prefer 8, 12, 16, 20, 24, 32, and 40px increments.
- Panel radius: 12px. Controls and badges: 5–7px. Keep corners modest and functional.
- Use borders (`--line`) for separation; avoid decorative drop shadows.
- Preserve the current 22px desktop panel gap and 20px mobile page gutter.

## Interface patterns

### Panels

Conversation, manager desk, and action history are peers in the operator workflow. Each panel needs a clear title, one-line purpose, and a visible empty state. Keep the panel header static while its contents scroll.

### Buttons

| Type | Use | Treatment |
| --- | --- | --- |
| Primary | One main action in a local context | Blue fill, white label, strong verb |
| Secondary | Reversible or supporting actions | White fill, blue/ink label, border |
| Quiet | Inline status or lightweight action | Text-only blue label |
| Destructive | Closing a case or other irreversible step | Ask for confirmation before use; never style like the primary send action |

Labels should begin with a verb: “Send message”, “Acknowledge case”, “Retry delivery”. Avoid vague labels such as “Submit” or “Continue”.

### Status and priority

Use a badge plus text, with a left ticket border as a secondary cue. Priority order is: `routine` → `medium` → `high` → `crisis`. A case may escalate automatically but should never visually appear less serious until it is closed by a manager.

### Empty, loading, and error states

- **Empty:** explain what will appear and what the user can do next.
- **Loading:** retain panel structure and show skeleton rows; do not replace the whole desk with a spinner.
- **Error:** name the failed action and give a recovery path. Example: “Couldn’t send this update. Check the local server, then retry.”
- **Delivery uncertainty:** use the existing explicit `uncertain` state. Never show it as sent.

## Accessibility baseline

- Meet WCAG 2.1 AA contrast: 4.5:1 for normal text; validate muted text against its actual background.
- Every keyboard-focusable control needs the existing visible amber focus ring or an equivalent 3px treatment.
- Keep keyboard focus in a confirmation dialog if one is added, then return focus to the triggering control.
- Use native buttons, labels, headings, form controls, and `aria-live` for new messages and errors.
- Do not auto-scroll a user away from text they are reading; only scroll the conversation when they are already at its end or after they send a message.
- Respect `prefers-reduced-motion`; do not make urgency depend on flashing or motion.

## Responsive behaviour

- Desktop: two equal desk columns, with action history below.
- Tablet and mobile: conversation first, manager desk second, action history last.
- Maintain a minimum 44 × 44px tap target for primary controls and give chip-style suggestions sufficient vertical padding.
- Let ticket metadata stack rather than compress when it no longer fits comfortably.

## Implementation checklist

- [ ] Keep all semantic colour values centralized as CSS custom properties.
- [ ] Add hover, active, disabled, and focus-visible states for every interactive control.
- [ ] Use a confirmation step before closing a case in the demo console.
- [ ] Add loading skeletons for the initial state refresh.
- [ ] Audit contrast after any palette change.
- [ ] Test the full rehearsal flow at 320px, 768px, and 1440px widths.
- [ ] Validate the keyboard-only flow: send report, acknowledge case, inspect history, close case.

## Font decision

The interface uses **Manrope** for all human-facing UI and **DM Mono** only for operational metadata.

| Font | Best use | Why |
| --- | --- | --- |
| Manrope | Headings, messages, controls, descriptions | Calm and modern without sacrificing compact control-label readability. |
| DM Mono | Ticket IDs, timestamps, delivery status, action payloads | Fixed-width characters make operational data easier to scan accurately. |
| Avenir Next / Segoe UI | Offline fallback | Reliable fallback when the hosted font is unavailable, but less distinctive and less consistent between devices. |
