# Chatbot component API and events

> Absorbed from Peter Armstrong's Logi Composer toolkit on 27 August 2026, source
> `peter-kb/bundle-2026-05-21/logi-composer-toolkit/docs/Composer-ChatBot-Embed-Guide.md`,
> which is itself transcribed from the embed SDK docs at
> `https://uat.logi-symphony.com/discovery/embed/docs/` (`Composer-ChatBot-Embed-Guide.md:3`).

`CHATBOT_EMBED.md` covers getting the bot on screen and keeping it there. This
file covers the object you get back: its class surface, the full event
vocabulary, and the shape of the payload that lets you turn a bot answer into a
real visual.

## The `EmbeddedChatBot` class

`embedManager.createComponent('chat-bot', config)` returns an `EmbeddedChatBot`,
which extends the base `EmbeddedComponent` (`Composer-ChatBot-Embed-Guide.md:11`).
There is a public constructor, positional rather than object-shaped:

```ts
new EmbeddedChatBot(
  theme: string,
  renderer: (component: EmbeddedComponent, element: HTMLElement) => void,
  config: ChatBotConfig,
  sources?: string[],
  instance?: EmbedManager,
  onClose?: () => void
): EmbeddedChatBot
```

(`Composer-ChatBot-Embed-Guide.md:69-77`). Peter says not to call it directly and
to go through `createComponent` instead (`Composer-ChatBot-Embed-Guide.md:79`).
The reason is not stated. Note that the constructor takes a `renderer` callback
that `createComponent` supplies for you, so calling it by hand means owning the
render pipeline as well; that reading is inference, not documented.

Two config types are in play and they nest. `ChatBotConfiguration` is the whole
object you hand to `createComponent`, and `ChatBotConfig` is the `config`
property inside it (`Composer-ChatBot-Embed-Guide.md:30-50`). Both are covered
field by field in `CHATBOT_EMBED.md`; nothing in Peter's tables contradicts them.

### Instance properties

Peter documents eleven readable properties on the returned object
(`Composer-ChatBot-Embed-Guide.md:83-96`). The ones worth reaching for:

| Property | Type | Use |
|---|---|---|
| `componentType` | `string` | Always `"chat-bot"`. Useful when you keep mixed components in one registry and need to branch. |
| `componentInstanceId` | `string` | Inherited unique id. This is the value `embedManager.publish()` wants in `targetComponents` when a page holds more than one embed. |
| `container` | `HTMLElement` | Set after `render()`. Absence is a cheap boot check. |
| `htmlElement` | `HTMLElement` | The root rendered element. |
| `loader` | `HTMLElement` | The loading overlay. |
| `isSymphonyMode` | `boolean \| undefined` | Inherited. Peter does not say what sets it or what it changes, so treat it as unverified. |

`config`, `sources`, `instance`, `onClose`, `theme` and `notificationSettings`
are also exposed, echoing back what you passed in.

### Methods beyond `render()`

`removeEventListener(eventName, callback)` takes the same function reference you
registered, so an inline arrow function cannot be unregistered
(`Composer-ChatBot-Embed-Guide.md:134-140`). Keep named handlers if you intend to
detach.

`getApplicationParams()` returns the resolved instantiation parameters:
`{ application, componentInstanceId, componentProps, notificationSettings, theme }`
(`Composer-ChatBot-Embed-Guide.md:163-170`). Peter marks it as primarily internal
and for debugging (`Composer-ChatBot-Embed-Guide.md:172`). It is the fastest way
to confirm from the console that the theme name and `apiBaseUrl` the SDK actually
resolved match what you thought you passed.

`removeLoader()` is inherited and fires automatically once rendering finishes
(`Composer-ChatBot-Embed-Guide.md:174-176`). Calling it yourself hides the
overlay without making the bot ready, so it hides a symptom rather than a state.

`destroy()` is covered under the contradiction below.

## `ChatBotEventNames`: all fifteen

Register with `addEventListener(eventName, callback)`. The typed parameter is
`ChatBotEventNames`, and the enum members can be used in place of the raw strings
(`Composer-ChatBot-Embed-Guide.md:115`, `Composer-ChatBot-Embed-Guide.md:182`).
Payload fields arrive on `e.detail`.

| Enum member | String value | Fires when | `e.detail` |
|---|---|---|---|
| `READY` | `composer-chat-bot-ready` | Bot is ready for interaction | (none) |
| `LOADED` | `composer-chat-bot-loaded` | Bot renders for the first time | (none) |
| `CLOSED` | `composer-chat-bot-closed` | User closes the bot | (none) |
| `FAILED` | `composer-chat-bot-failed` | Bot fails to initialise or load | `{ failedReason }` |
| `MESSAGE_SENT` | `composer-chat-message-sent` | User sends a message | `{ text }` |
| `MESSAGE_RECEIVED` | `composer-chat-message-received` | Bot returns a response message | `{ text }` |
| `MESSAGE_ABORTED` | `composer-chat-message-aborted` | A message request is aborted | `{ text }` |
| `MESSAGE_TIMEOUT` | `composer-chat-message-timeout` | A message request times out | `{ text }` |
| `MESSAGE_ERROR` | `composer-chat-message-error` | Error while processing a message | `{ text, failedReason }` |
| `MESSAGE_COPIED` | `composer-chat-message-copied` | User copies a message to the clipboard | `{ text }` |
| `MESSAGE_UPVOTED` | `composer-chat-message-upvoted` | User upvotes a response | `{ recordId, feedbackType }` |
| `MESSAGE_DOWNVOTED` | `composer-chat-message-downvoted` | User downvotes a response | `{ recordId, feedbackType }` |
| `VISUAL_RECEIVED` | `composer-chat-visual-received` | A visual response arrives | `{ visParams }` |
| `VISUAL_ACTION_EXECUTED` | `composer-chat-visual-action-executed` | User executes a visual action, for example save to dashboard | `{ visual }` |
| `SUGGESTIONS_FAILED` | `composer-bot-suggestions-failed` | Fetching suggestions fails | `{ failedReason }` |

Source: `Composer-ChatBot-Embed-Guide.md:186-200`.

### The prefix trap

Fourteen of the fifteen strings begin `composer-chat-`. `SUGGESTIONS_FAILED` is
`composer-bot-suggestions-failed`, with `bot` where the others have `chat`
(`Composer-ChatBot-Embed-Guide.md:200`). Any loop that builds names from a
`composer-chat-` stem, or any grep that filters on that stem, silently drops it,
and the failure looks like suggestions simply never failing. Enumerate the
strings explicitly, or use the enum members and let the SDK supply the values.

### Which ones earn a handler

`MESSAGE_TIMEOUT` and `MESSAGE_ABORTED` both surface as a dead reply in the UI
with no error banner, so wire them if you want a demo that explains itself
instead of appearing to hang. `timeout` defaults to 30 seconds, which NLQ
round-trips exceed regularly.

`MESSAGE_UPVOTED` and `MESSAGE_DOWNVOTED` carry `recordId` and `feedbackType`
rather than the message text, so a feedback log built from them alone cannot
reconstruct what was rated. Pair each with the `MESSAGE_RECEIVED` text you
already hold. What `feedbackType` contains beyond the up or down distinction is
not documented, and I have not verified it.

`CLOSED` fires alongside the `onClose` callback. Peter documents both without
saying whether one is a superset of the other, so pick one path for panel state
and leave the other for telemetry rather than running both.

## `visParams` extraction

`visParams` is the payload of `composer-chat-visual-received` and the object that
turns a chat answer into something you can open, filter with, or save. Peter
records its top-level shape as verified from a live session
(`Composer-ChatBot-Embed-Guide.md:204-239`): two branches, `visual_request`
(what was asked of the visual engine) and `visual_response` (what came back).

```json
{
  "visual_request": {
    "sourceId": "<source-id>",
    "visualTypeId": "<visual-type-id>",
    "visualNamePrefix": "generated",
    "description": "Visual created from query: <user prompt>",
    "tags": ["generated"],
    "metrics": [{ "name": "ad_revenue_eur", "func": "sum" }],
    "dimensions": [{ "name": "campaign_name" }],
    "timeFilter": { "from": "+$start_of_data", "to": "+$end_of_data", "timeField": "dt" }
  },
  "visual_response": {
    "visId": "<visual-id>",
    "type": "UBER_BARS",
    "visualName": "generated_<uuid>",
    "source": { "variables": { "Multi Group By": [{ "name": "campaign_name" }] } }
  }
}
```

The verified paths (`Composer-ChatBot-Embed-Guide.md:243-249`):

| What you want | Path |
|---|---|
| First dimension field name | `visParams.visual_request.dimensions[0].name` |
| All dimensions | `visParams.visual_request.dimensions`, array of `{ name }` |
| All metrics | `visParams.visual_request.metrics`, array of `{ name, func }` |
| Time filter range | `visParams.visual_request.timeFilter` |
| Simba-assigned visual name | `visParams.visual_response.visualName` |

Field names here are physical field names as the source defines them, not the
display labels a dashboard shows. That distinction is what the mapping step below
exists to bridge.

`visual_response.visId` and `visual_response.type` appear in the sample but Peter
gives no extraction guidance for them. `visId` looks like the handle you would
use to open the visual without a name lookup, which would be shorter than the
save-then-resolve-by-name flow in `CHATBOT_EMBED.md`, but I have not tested
whether it resolves before the visual is saved. Treat it as unverified.

### Filtering a dashboard from `visParams`

Peter's recipe (`Composer-ChatBot-Embed-Guide.md:253-258`):

1. Pull the first dimension, for example `campaign_name`, from
   `visParams.visual_request.dimensions[0].name`.
2. Map that physical field name to the Cross-Source Link label on the target
   dashboard, for example `{ campaign_name: "Campaign Name" }`.
3. Publish on the label:
   `embedManager.publish("Campaign Name", { type: 'selection', valueType: 'ATTRIBUTE', ranges: [] })`.

The prerequisite is the part that costs an afternoon: the Cross-Source Link must
already exist in Composer, created in the dashboard editor under Interactions,
Cross-Source Links, with that label mapped to that field. Without it,
`embedManager.publish()` returns without error and nothing happens
(`Composer-ChatBot-Embed-Guide.md:258`). The publish topic is the link label, so
publishing the raw field name fails the same silent way.

On a page with more than one embedded dashboard, pass
`{ targetComponents: [componentInstanceId] }` as the third argument, or the
filter reaches every embed on the page. That comes from the embed manager
behaviour in `EMBEDDING.md`, not from Peter's chatbot guide.

Peter's step 3 publishes an empty `ranges: []`, which selects nothing concrete.
The example demonstrates the call shape rather than a working filter, and the
guide does not show how the dimension's value gets into the payload. Unverified,
and worth resolving against a live instance before relying on it.

## Where Peter's guide contradicts itself: `destroy()` versus render-once

Peter's worked example closes the bot by hiding the panel with `display: none`
and calling `destroy()`, then nulling the reference so the next open recreates
the component from scratch (`Composer-ChatBot-Embed-Guide.md:323-331`, with the
same instruction stated as a rule at `Composer-ChatBot-Embed-Guide.md:148` and
`Composer-ChatBot-Embed-Guide.md:339`).

`CHATBOT_EMBED.md:133-144` forbids that shape and attributes the endless "Loading
Assistant" spinner to it, on two counts: a `display: none` panel has zero
dimensions so the SDK cannot measure its container, and re-initialising a
component that has already booted aborts the in-flight SDK requests.

This is a disagreement inside Peter's own material rather than between the two
knowledge bases. His Stitch guide states the render-once rule directly, three
times:
`Demo Builder/COMPOSER-EMBED-IN-STITCH.md:1815` calls re-rendering an initialised
chatbot critical to avoid and names the endless spinner as the consequence;
`COMPOSER-EMBED-IN-STITCH.md:1845` marks the single render call in the boot
function; `COMPOSER-EMBED-IN-STITCH.md:1871` restates it as a key rule, boot once
and toggle with CSS. The same section bans `display: none` and `hidden` on the
panel for the zero-dimension reason, prescribing `opacity-0 pointer-events-none`
instead.

Follow the Stitch pattern. Boot on auth ready, render once into a container that
always has real dimensions, toggle visibility with opacity, and keep the
reference alive across close and reopen.

`destroy()` still has a job, and Peter's underlying claim at
`Composer-ChatBot-Embed-Guide.md:339` is sound: skipping it leaves orphaned
listeners and an open WebSocket. The correct trigger is genuine teardown, meaning
the host page or route is unmounting and the container is going away for good.
Closing a panel the user will reopen in ten seconds is not teardown. Reading
`destroy()` as a close handler is what makes the two documents collide.

Peter's `openChatbot` already guards with an early return when the reference
exists (`Composer-ChatBot-Embed-Guide.md:271`), so the example is one step from
correct: keep the guard, drop the `destroy()` from close, and swap `display` for
`opacity`.
