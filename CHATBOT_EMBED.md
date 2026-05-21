# Embedding the Simba Intelligence chatbot

Simba Intelligence (SI) is insightsoftware's AI semantic-layer product. Its
chatbot does natural-language query (NLQ) over the SI semantic layer and
returns either text or an AI-generated visual. You embed it through the SAME
Composer embed manager you use for dashboards (see `EMBEDDING.md`), as a
component of type `chat-bot`. There is no second SDK to load.

```js
const chatBot = embedManager.createComponent('chat-bot', {
  sources: ['<sourceId>'],
  theme: 'dark',
  config: {
    apiBaseUrl: '<server>/intelligence',
    timeout: 60,
    mode: 'auto',
    allowModeSwitch: true,
  },
  onClose: closeChatbot,
});
chatBot.render(document.getElementById('chatbot-container'), {});
```

The chatbot is governed. `sources` is the semantic-layer context the bot is
allowed to query, and every query runs under the embed session's identity, so
row-level security and column security apply per query exactly as they do for an
embedded dashboard. You cannot ask the bot for data the session can't see.

## The component config

`createComponent('chat-bot', ...)` takes a `ChatBotConfiguration`:

| Field | Type | Required | What it does |
|---|---|---|---|
| `sources` | `string[]` | yes | Source ids the bot may query. This is the semantic-layer / RLS context. |
| `config` | `ChatBotConfig` | yes | Behaviour settings, see below. |
| `theme` | `string` | no | Theme name. See "themes" below. |
| `instance` | `EmbedManager` | no | Pass the embed manager to let the bot embed live Composer visuals inline inside chat responses. |
| `notificationSettings` | object | no | Toast/notification display settings. |
| `onClose` | `() => void` | no | Close callback. Dual role, see "onClose and destroy" below. |

`config` (the `ChatBotConfig` sub-object):

| Field | Type | Default | What it does |
|---|---|---|---|
| `apiBaseUrl` | `string` | (required) | The SI API endpoint. Always the `/intelligence` path on the same server, e.g. `<server>/intelligence`. |
| `timeout` | `number` | `30` | Per-request timeout in seconds. NLQ round-trips are slow; `60` is a sensible demo value. |
| `mode` | `'none' \| 'auto' \| 'visual'` | `'none'` | How responses render, see below. |
| `allowModeSwitch` | `boolean` | `false` | If `true`, the user gets a UI toggle to change `mode` inside the chat. |

## Modes

| Value | Behaviour |
|---|---|
| `none` | Text-only. Any visual the model proposes is dropped. This is the default, which is why a fresh embed never shows charts. |
| `auto` | The model decides per answer whether a visual helps. Returns a visual when relevant, otherwise text. Use this for demos. |
| `visual` | Always returns a visual plus a summary line. |

The default of `none` is the silent gotcha: leave `mode` unset and you get a
text-only bot, then waste time wondering why no charts appear. Set `auto`.

## Themes

Documented theme values are `composer`, `modern`, and `dark`. A custom Composer
theme name also works, but ONLY if that theme's JSON includes a `symphony`
section. Without the `symphony` section the bot silently ignores the named theme
and falls back to its internal defaults, so a brand-matched dashboard ends up
next to an off-brand chatbot and nothing errors. If you pass a custom theme,
confirm the `symphony` section exists first. `modern` is a safe fallback.

## Events

The bot dispatches DOM-style events you wire with `addEventListener`. The
`e.detail` payload differs per event. The ones worth handling:

| String value | Fires when | `e.detail` |
|---|---|---|
| `composer-chat-bot-loaded` | The bot UI finishes initialising the first time | (none) |
| `composer-chat-bot-ready` | The bot is ready for interaction | (none) |
| `composer-chat-bot-failed` | The bot fails to init or load | `{ failedReason }` |
| `composer-chat-message-sent` | The user sends a message | `{ text }` |
| `composer-chat-message-received` | The bot returns a text response | `{ text }` |
| `composer-chat-message-error` | A message errors during processing | `{ text, failedReason }` |
| `composer-chat-visual-received` | The bot returns a visual suggestion | `{ visParams }` |
| `composer-chat-visual-action-executed` | The user executes a visual action (e.g. save) | `{ visual }` |

The NLQ text the user typed is on the visual-received event at
`e.detail.visParams.visual_request.description`. It is usually prefixed with
`Visual created from query: `, so strip that before showing it as a title.

```js
chatBot.addEventListener('composer-chat-bot-loaded', () => {
  // reveal your toggle button now, not before, see "loading pitfalls"
});

chatBot.addEventListener('composer-chat-visual-received', (e) => {
  const vp = e.detail.visParams;
  const title = (vp.visual_request.description || '')
    .replace(/^Visual created from query:\s*/i, '')
    .trim() || 'AI generated visual';
  // show an "open visual" affordance with this title
});

chatBot.addEventListener('composer-chat-visual-action-executed', (e) => {
  // e.detail.visual.visualName is the saved gallery name
});
```

### Opening an AI-generated chart in the visual builder

A common next step is letting the user open the bot's chart full-screen to
explore and save it. The flow:

1. On `composer-chat-visual-received`, cache `e.detail.visParams` and derive the
   human-readable title from `visParams.visual_request.description`.
2. When the user opens it, trigger a save (the bot's own save action) so the
   visual exists in the gallery, then resolve its id by name via
   `GET <server>/discovery/api/visuals?name=<name>&size=1`. Use the
   `/discovery/api` prefix; the bare `/api` path is CORS-blocked from the browser
   (see `WRITEBACK_ODATA.md`).
3. Render `createComponent('visual-builder', { visualId, ... })` into a
   full-screen overlay.

`composer-chat-visual-action-executed` carries the saved name in
`e.detail.visual.visualName`; fall back to
`visParams.visual_response.visualName` if the event does not fire.

## Loading pitfalls

These are the hard-won ones. They do not error; they spin forever on "Loading
Assistant" or quietly misbehave.

* **Never `display:none` the panel.** A hidden panel has zero dimensions, the SDK
  cannot measure its container, and it spins forever. Hide the panel with
  `opacity: 0; pointer-events: none` instead so it keeps real layout dimensions
  while invisible. Same failure mode as zero-height embedded widgets in
  `EMBEDDING.md`.
* **Render once only.** Calling `render()` a second time on an already-initialised
  component aborts all in-flight SDK requests and forces a re-init, which lands
  you back on the endless spinner. Boot once, then toggle the panel with CSS.
* **Boot on auth-ready, not on first open.** Create and render the component as
  soon as auth is ready, while the panel is still `opacity: 0`. Reveal the toggle
  button only when `composer-chat-bot-loaded` fires, so the user never clicks
  into a component that is not ready. The bot warms up in the background.
* **Set `_isDrawerEmbed: true` on the ref.** If your shell intercepts WebSocket
  `START_VIS` messages to inject dashboard filters (the fallback filtering
  pattern), that injector will bleed the main dashboard's filters into the
  chatbot's own WebSocket connection. Tagging the ref `_isDrawerEmbed: true`
  excludes it from filter injection.
* **Three `#logi-modal-root` CSS overrides.** The bot uses Blueprint portal
  popups (e.g. the plus-button menu). The SDK appends those portals to
  `#logi-modal-root`, a div injected as a DIRECT child of `<body>`, NOT inside
  your chatbot container. So the overrides must target `#logi-modal-root`, not
  the container:

  ```css
  /* 1. SDK root clips popup content */
  .logi-embed.logi-embed-main { overflow: visible !important; }
  /* 2. Blueprint overlay wrapper inside the portal also clips */
  #logi-modal-root .bp3-overlay { overflow: visible !important; }
  /* 3. portal z-index is 5000; a chatbot panel at z-9998 paints over it.
     push the portal above the panel (and your modals). */
  #logi-modal-root .bp3-portal { z-index: 10000 !important; }
  ```

  Float the panel below modals: panel at `z-index: 9998`, modals at `9999`, the
  portal override at `10000` so popup menus clear both.

## onClose and destroy

`onClose` has a dual role. It is the close callback AND it controls whether the
bot renders its own close button. Omit `onClose` and there is no close button at
all. Provide it both to get the button and to sync your own panel state when the
user clicks it (e.g. flip your toggle back to closed).

`destroy()` is mandatory on teardown. Always call it BEFORE removing the
container from the DOM. Skipping it leaks event listeners and orphans the
WebSocket connection.

```js
function closeChatbot() {
  document.getElementById('chatbot-panel').style.display = 'none';
  if (chatBotRef) {
    chatBotRef.destroy();   // before removing from the DOM
    chatBotRef = null;
  }
}
```

## Sources

* "Embed SI on symphony playground" (CMP-9046):
  https://insightsoftware.atlassian.net/wiki/spaces/DCI/pages/17862524939
* EmbedManager:
  https://insightsoftware.atlassian.net/wiki/spaces/ZD/pages/15459516960/EmbedManager
