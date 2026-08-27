# Graph

Nodes, one absorption target each. None reads another's output, so all run at once.
Each writes exactly one new file, so there is no merge to resolve.

| node | writes | absorbs from Peter |
|---|---|---|
| P1 | `EMBEDDING_API.md` | Embedding reference sections 8 to 13: PublicationOptions, publisherId, targetComponents, the confirmed-not-working list |
| P2 | `CHATBOT_EVENTS.md` | ChatBot embed guide: EmbeddedChatBot class, all 15 event names, visParams extraction |
| P3 | `CHATBOT_THEMING.md` | Theme guide lines 185 to 262: the symphony layer, 12 token groups, 16 chatBot properties |
| P4 | `VISUAL_TYPES.md` | Visual types guide: the type ID quick reference and per-type config shapes |
| P5 | `CUSTOM_METRICS.md` | Custom metrics guide: endpoint and expression syntax |
| P6 | `SECURITY_ANSWERS.md` | The 26 RFP requirements, plus the complete auth-mode inventory at :485 |
| P7 | `DISCLOSURE.md` | The public / internal / NDA tagging scheme, adapted to sit beside truth grading |
| X1 | `BEYOND_PARITY.md` | What NEITHER side had, from Confluence: 26.3 topology, the auth-stack rebuild, token revocation, the 26.2 API delta |

X1 exceeds parity rather than reaching it, and has no edge to P1 to P7 either.
