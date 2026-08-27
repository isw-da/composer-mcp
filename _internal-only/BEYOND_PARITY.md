# Beyond parity

Everything here comes from insightsoftware Confluence and Jira, and was absent from both
Amin's `composer-mcp` docs and Peter's toolkit bundle when the comparison ran on
27 August 2026. Every claim carries a Confluence page id or a Jira key. Read the cited
page before acting on anything expensive: several are drafts, and two self-contradict.

Confluence cloud id `3df814b7-ac56-4f3f-b457-fa981a2a59ef`. All pages read on
27 August 2026.

---

## 1. The one that breaks working code: SI moves off `/` in 26.3

**Source: page 18711380170, "Simba Intelligence + Composer Deployment Scenarios (draft)",
space SCP, last modified 26 August 2026.**

| | 26.2 (Q2) | 26.3 (Q3+) |
| --- | --- | --- |
| SI path | root `/`, Composer at `/discovery`, MCP at `/mcp` | `{composer-context}/intelligence`, default `/composer/intelligence` |
| Helm | separate SI chart required | SI is a sub-component of the Composer chart, no separate chart |
| Composer hosted separately, SI pointing at it | supported | "Configuration no longer supported in 26.3+" |

The context path stays configurable. The page names `/composer` as the default and says an
admin may set `/discovery`, `/analytics` or anything else at deployment time. So `/discovery`
survives only where somebody deliberately configures it, and stops being the shape you get
by default.

### Why 26.2 looks the way it does

Page 18711380170 attributes the 26.2 layout to Terrence, and gives two reasons the Composer
Helm chart could not simply proxy SI:

1. SI uses React Router, which does not support dynamic sub paths. That forced SI to the root
   path, pushing Composer to `/discovery` and MCP to `/mcp`, with an ingress proxying between
   two separately deployed products.
2. The Composer chart had no awareness of SI. The old Symphony chart had a flag to deploy SI;
   the Composer chart did not. The SI chart, by contrast, knows about Composer and can deploy
   or point at it.

26.3 dissolves both by making SI a sub-component of the Composer chart.

### What this invalidates locally

* **`otto-composer/otto-opc-shell.html` line 1066** hardcodes
  `composerApiUrl: 'https://uat.logi-symphony.com/discovery'`. On a 26.3 unified deployment
  that URL is wrong unless the admin explicitly set the context path to `/discovery`.
  Seven other files in that repo carry the same literal: `reauthor_and_tag.py:21`,
  `serve_nocache.py:32`, `create_si_connections.py:14`, `cleanup_migration_litter.py:12`,
  `create_bq_connection.py:7`, `consolidate_dashboard.py:26`, `migrate_otto_to_vdd.py:33`,
  plus `.env.example:7`. Make the context path one variable and read it from the environment.
* **`EMBEDDING.md` line 58** shows `<script src="/discovery/embed/embed.js">`. Under 26.3
  that becomes `{composer-context}/embed/embed.js`.
* **`CHATBOT_EMBED.md` lines 118 to 119** instruct callers to use the `/discovery/api` prefix
  because the bare `/api` path is CORS-blocked from a browser. The CORS reasoning holds; the
  literal prefix does not.
* **`README.md` lines 76, 159 and 197** and **`SCHEMA_NOTES.md` line 14** present `/discovery`
  as *the* bundled-deployment context path. Reframe as "26.2 default, configurable, and no
  longer the 26.3 default".
* **`SAFETY.md` lines 33, 120 and 221** use `/discovery/...` URLs in recovery instructions.
* **`LIMITATIONS.md` line 112** cites reading `/discovery/embed/embed.js` as evidence. The
  evidence still stands; annotate the path.

### The page contradicts itself, so do not quote its FAQ

Page 18711380170 is marked draft, and its FAQ still carries the 26.2-era answer alongside the
26.3 body. The FAQ says the recommended path is to "Use the **SI helm only**" and that
"All AI features from SI will only work at the new SI URL with `/discovery`". The body of the
same page deprecates that chart. A later FAQ entry acknowledges the collision ("Does Q3+
change how this works?") without editing the earlier answer. Treat the tables as current and
the FAQ as historical. Anyone quoting this page to a customer should say which half they read.

The page also says the transition guide lives "at location", with no link. That guide does not
yet exist in a form this node could find.

### URL visibility

Page 18711380170 says `/intelligence` is mostly internal. A user driving SI features through
the Composer UI stays at `https://abc.com/composer` in the address bar. The path matters for
REST callers and for bookmarks, not for what a demo audience sees. Example endpoints given:
`GET https://abc.com/composer/intelligence/api/sources` and
`POST https://abc.com/composer/intelligence/api/chat`.

---

## 2. The auth stack was rebuilt from scratch, twice

**Sources: page 17512824891 (Spring Boot 2.7 to 3.x, 22 October 2025), page 18519490785
(Spring Boot 3.5.5 to 4.0.6, 7 July 2026), page 18520178765 (OAuth2 legacy library removal,
7 July 2026).**

Composer's OAuth2 and Trusted Access implementation has been rewritten twice inside roughly
twenty months, and the second rewrite removed `spring-security-oauth2` 2.5.2.RELEASE entirely.

**Why this matters more than the endpoint list.** `SCHEMA_NOTES.md` was written by probing a
live v25 instance and recording what came back: which auth mode works, which 403s, which 500s,
what the push-token body must contain. Every one of those behaviours now sits on a
reimplemented stack. All three pages claim behaviour preservation, and page 17512824891 grades
its own migration "A+ (95/100)". A self-graded claim of behaviour preservation is a hypothesis,
not a test result. Re-probe rather than assume.

### What was removed and replaced (page 18520178765)

The legacy Spring types are gone: `TokenStore`, `OAuth2Authentication`, `OAuth2AccessToken`,
`DefaultOAuth2AccessToken`, `OAuth2RefreshToken`, `AuthenticationKeyGenerator`,
`ResourceServerTokenServices`, `ClientDetailsService`, `ClientDetails` / `BaseClientDetails`,
`OAuth2MethodSecurityExpressionHandler`, `OAuth2Exception`, `InvalidTokenException`,
`OAuth2AuthenticationDetails`. In their place: a `ZoomdataTokenStore` interface working
directly on the existing `OAuth2Token` JPA entity, plus three replacement exception classes
under `com.zoomdata.model.security.oauth2`.

Page 18520178765 states the database schema and the REST API contracts are unchanged.

### The behavioural changes it does admit

Page 18520178765 lists these in its own risk table, so they are not speculation:

* **Auth key format changed** from an MD5 hash to the plain string `clientId + "|" + username`.
  Tokens minted before the change cannot be found by `getAccessToken()`, so a duplicate token
  gets minted instead of the existing one being reused. Rated Low. It still means token counts
  can jump across an upgrade.
* **Activity logging lost a type.** Token-based auth now returns a
  `UsernamePasswordAuthenticationToken`, the same type password login returns, so the success
  listener can no longer tag events `TRUSTED_ACCESS`. If you audit Composer login events by
  authentication type, that column degrades.
* **`TrustedAccessLicenseExpirationException` changed parent class**, which changes the error
  serialisation in the HTTP response. Rated Medium.
* **External OAuth2 login** (Google, Azure AD) swapped
  `DefaultAuthorizationCodeTokenResponseClient` for
  `RestClientAuthorizationCodeTokenResponseClient`, a different HTTP client underneath.
  Rated Medium.

### Two more from the framework upgrade (page 18519490785)

* **Trailing slashes stop matching.** `setUseTrailingSlashMatch(true)` was removed in Spring
  Framework 7, so `/api/users/` no longer resolves to `/api/users`. Any SDK or script that
  appends a slash breaks. The page flags this as a risk item for its own stage 3 testing.
* **A path matcher was widened.** `AntPathRequestMatcher` gave way to
  `PathPatternRequestMatcher`, which does not accept `**` followed by a wildcarded segment.
  The pattern `/api/visual-types/**/*.js` had to become `/api/visual-types/**`. Page 18519490785
  calls this out itself: "This is a slight security consideration (now permits any file
  extension, not just `.js`)."

### One thing that has not changed and is easy to misread

Lazy token cleanup. Page 17513939046 test case 1.5.2 says expired tokens stay in the
`oauth_tokens` table until somebody tries to use them, at which point they are deleted. That is
labelled expected behaviour matching Spring Boot 2.7, not a bug. Page 17512824891 separately
flags that `removeExpiredTokens()` exists with no visible `@Scheduled` caller, and lists
verifying a scheduled cleanup job as an open action item. Both readings coexist in the
corpus; the QA page is the more recent and more specific of the two.

### What to do locally

Add a dated caveat at the top of `SCHEMA_NOTES.md` saying the observations were taken against
a v25 instance, and that the auth stack underneath was rebuilt for Spring Boot 4.0 (pages
18519490785 and 18520178765). Re-run the trusted-access probes against 26.2 or later before
quoting any of it as current behaviour.

---

## 3. Trusted access tokens can be revoked, and the endpoint is public

**Source: page 17296556033, "CMP-6752: Revoke Composer Trusted Access Token", space ZD,
last modified 31 July 2025. Jira: CMP-6752.**

`DELETE /api/trusted-access/tokens/{tokenId}`

`si-docs-mirror/composer-api/ENDPOINTS.md` line 494 already lists this endpoint. What neither
knowledge base carried is the operating detail, all of which comes from page 17296556033:

* **Authentication is client id and client secret**, the same trusted-access client credentials
  used to mint the token. Not a user session, and not a bearer token.
* **Success returns 204 No Content** with an empty response object and no response headers.
* **Failure is 403 Access Denied.** That is the only error code the page documents.
* **"Hide for Customer from Swagger: No".** The endpoint is visible in the customer-facing
  Swagger, so it is fair game in a security questionnaire answer.
* **Path variable only.** No query parameters, no request headers, no request body.
* The change is additive: "New Api created no impact on existing apis".

This is the answer to "can you revoke a session token if an embedded user is terminated
mid-session". Amin's `SCHEMA_NOTES.md` covers minting tokens and never covers revoking them.
Worth adding to `SCHEMA_NOTES.md` under the existing Trusted Access section, and to any
security-questionnaire response covering session termination.

---

## 4. The v25 to v26 REST delta is narrow and additive

**Source: page 18056609793, "26.2 API Changes", space ZD, last modified 17 June 2026.**

The full table, verbatim in substance, four rows and nothing else:

| Endpoint | Sprint | Change | Method |
| --- | --- | --- | --- |
| `api/export/visualdata/enriched` | (blank) | CREATE | POST |
| `api/dashboards/{dashboardId}/reports` and `api/dashboards/{dashboardId}/reports/{reportId}` | 26.2/1 | Update | POST/PUT |
| `/api/self-service-reports/export` | 26.2/3 | Update | POST |
| `api/dashboards/{dashboardId}/reports` and `api/dashboards/{dashboardId}/reports/{reportId}` | 26.2/3 | Update | POST/PUT |

One new endpoint, and the dashboard reports pair updated in two separate sprints. Each row
links to its own API change approval page (18056609805 for the enriched export, 18115887105
and two tiny links for the reports and self-service-reports updates). This node did not open
those four child pages, so the field-level detail of each update is uncaptured.

The useful conclusion for anyone maintaining an MCP wrapper: the endpoint shape barely moved
between 25 and 26. The topology moved (section 1) and the auth stack moved (section 2).
A v25-era client that only calls REST endpoints will mostly keep working; a v25-era client
that hardcodes a context path or depends on observed auth behaviour will not.

---

## 5. The supported auth-mode inventory, and an X.509 recipe that ran

**Sources: page 17513939046, "Zoomdata Server Spring Boot Upgrade: Security related testing
scope", space ZD, 7 January 2026. Page 18663243796, "X.509 Authentication Testing, Logi
Composer (QA Runbook)", space SCP, 12 August 2026.**

Page 17513939046 is a 21-section QA guide covering the complete authentication surface, which
makes it the best single answer to "what auth modes does Composer support" in a security
questionnaire. The modes, each with its enabling property where the page gives one:

| Mode | Property | Notes from page 17513939046 |
| --- | --- | --- |
| OAuth2 / Trusted Access | `security.global.trusted_access` | Pull and push token models; default token validity 1800 seconds, from `server.session.timeout` |
| Form login | (default) | `POST /j_spring_security_check`; remember-me cookie valid 31536000 seconds |
| Basic auth | (section 3) | API access |
| LDAP | `security.global.ldap` | Auto-provisioning, group to role mapping, role hierarchy admin > supervisor > user |
| Kerberos / SPNEGO | `security.global.kerberos` | Keytab-validated, falls back to form login when no ticket is presented |
| X.509 | `security.global.x509` | Principal extracted by `X509ZdPrincipalExtractor`; no auto-provisioning unless configured |
| SAML | (not stated) | Section 21 exists, but the guide's own header says "SAML not covered yet" |

Non-obvious constraints worth quoting into a questionnaire, all from page 17513939046:

* **Supervisor users cannot use trusted access.** Test case 1.1.6 expects 403 with "The target
  user is a supervisor".
* **With trusted access disabled, only system clients can mint tokens** (`isSystem=true`), and
  that path exists specifically so dashboard reporting keeps working. Non-system clients get
  "Client not valid".
* **Expired tokens are deleted on access, not on a schedule.** See section 2 above.
* **The `/oauth/token` and `/oauth/authorize` endpoints only come into play with Snowflake and
  BigQuery connections**, per a note attributed to Rajesh Punna in section 1.6.

### The X.509 runbook

Page 18663243796 is a passed test run against **build 26.3.0** on 10 August 2026, five test
cases, all PASS. It is a working recipe rather than a specification, and it captures gotchas
that cost hours:

* Port stays **8080** after SSL is enabled, not 8443.
* `security.global.x509=true` is required **in addition to** the `server.ssl.*` properties.
  SSL alone does not give you X.509 auto-login.
* The target user must exist in Composer **before** SSL is enabled.
* `keytool` is not on the host; use the one inside the container at
  `/opt/java/openjdk/bin/keytool`. JKS files belong at `/etc/zoomdata/` inside the container.
* With `server.ssl.client-auth=want` the client certificate is optional, which gives you a
  clean two-browser demo: a profile holding the certificate auto-logs in as that user, a
  profile without one falls back to the normal login form.
* Permission changes made by an admin in one browser take effect in the certificate-authenticated
  session on a plain F5, with no re-authentication (test case TC-5 part B).

The runbook contains working credentials and passphrases for a test EC2 instance
(`10.2.7.86`). Do not copy those into anything customer-facing.

---

## 6. The 67-tag API criticality matrix

**Source: page 17738268781, "Complete API Technical Impact Analysis", space ZD, 9 December
2025. Marked Status: DRAFT.**

This page grades all 67 Swagger tag groups against a proposed project and folder hierarchy
layer (Tenant, Project, Folder, Object, replacing flat tenant scoping). Its headline: 20
critically impacted endpoints, 15 high-severity modifications, 12 new APIs required, roughly
75% of the existing API surface affected.

The bands, which are the reusable part:

* **Critical, breaking:** `inventory`, `permissions`, `dashboards`, `sources`,
  `sources / security`, `sources / security / row`, `dashboard-sharing`, `security`.
* **High, partially breaking:** `groups`, `dashboard-reports`, `jobs`, `export`,
  `sources / migration`, `dashboard-migration`, `sources / security / fields`.
* **Medium, additive:** twenty-odd tags gaining an optional `projectId` filter, among them
  `favorites`, `tags`, `comments`, `filter-sets`, `connections`, `uploads`, `alerts`,
  `activity`, `odata`, `self-service-reports`, `joins`, `sources / custom-metrics`.
* **Low, unchanged:** `connectors`, `accounts / users`, `accounts / admins`, `register`,
  `branding`, `version`, `license`, `timezones`, `keyset`, `calendars`,
  `sources / dictionaries`, `sources / unique-key`, `connection-types`,
  `dashboard-conversion`.

Two changes in the proposal would alter semantics an MCP wrapper depends on:

1. **Permission resolution flips from "most permissive wins" to "any deny wins".** Current
   Composer computes `MAX(tenant, group, user)`. The proposal walks the inheritance chain and
   returns NONE if any node denies. Levels go from three (Read, Write, Delete) to seven
   (NONE, VIEW, EXPORT, EXECUTE, CREATE, MODIFY, FULL_CONTROL).
2. **Parallel API versions.** `/api/v1/...` stays legacy and, the page commits, is maintained
   indefinitely with Default Project implied. `/api/v2/...` becomes project-aware.

None of this has shipped. The page is a draft impact assessment for a proposal, and every
timeline in it is expressed in relative months rather than dates. Read it as a warning about
where the permissions model is heading, not as a description of any released build. Its
backward-compatibility commitment is the sentence to remember: existing content stays in a
Default Project with unchanged permissions and v1 calls keep working.

Amin's `LIMITATIONS.md` already documents which endpoints the MCP does not wrap. If the v2
split lands, that file needs a version column.

---

## 7. Where the product boundary now sits

**Source: page 18211831886, "Composer Dundas Product Vision", space DCI, 19 May 2026.**

Logi Symphony simplification completed at the end of Q2 2026, splitting Composer and Dundas
into independent products. The persona boundary is stated flatly enough to quote in a
qualification call:

| | Composer | Dundas |
| --- | --- | --- |
| Built for | AI agents and humans; the platform layer that Simba Intelligence and third-party agents consume | Exclusively humans; data builders, report developers, power analysts |
| Data layer | Semantic layer (business context, governed access, AI-ready metadata) | Data cubes (ETL, aggregation, OLAP, scripting, in-memory blending) |
| Embedding | Direct SDK, no iframe, white-label, multi-tenant, described as the core moat | Embeddable via API or iframe |
| Visualisation | eCharts catalogue, self-service VDD, embeddable widgets | Deep customisation with layers and JavaScript, managed dashboards and reports |

### The reciprocal ceiling, which is the useful half

Page 18211831886 has a "what it does not mean" section that draws limits in both directions:

* **Dundas is not building AI, NLQ or agentic features.** Where AI is needed on a Dundas
  surface, it flows through Composer's platform layer, with Simba Intelligence consuming
  Composer APIs.
* **Composer is not building a deep data cube engine or ETL orchestration.** Heavy data
  modelling is Dundas's job.
* **Pixel-perfect reporting moves to Logi Report.** Dundas is not to extend server-side
  reporting beyond managed dashboard and report fidelity.
* **Neither product chases feature parity with Exago, Izenda or Logi Info** where the
  portfolio already covers the functionality.

Composer's near-term priorities, per the same page: sub-tenant isolation and multi-tenancy
governance (named customers Damstra, Encompass, Hoodie Analytics); object and folder
organisation, which is the same project layer page 17738268781 is assessing; visualisation
catalogue expansion; and semantic-layer work split by language, Java on Composer and Python
on SI.

---

## 8. A renaming that has not been approved

**Source: page 18628608081, "Product Hierarchy Changes", a live page in Alison Huselid's
personal space, 4 August 2026. Its first line reads: "Not yet approved - input provided into
2027 annual planning".**

Flagged as unapproved. Do not use these names with a customer, and do not update the naming
rules in `CLAUDE.md` on the strength of this page.

| FY27 product family | FY27 product line | Change |
| --- | --- | --- |
| Simba Intelligence | Agentic Intelligence | formerly Simba Intelligence |
| Embedded Analytics | Self-Serve Analytics | formerly Logi Composer |
| Embedded Analytics | Custom Analytics | formerly Dundas |
| Embedded Analytics | Pixel Perfect Reporting | formerly Logi Report |
| Data Connectivity | Core Drivers | formerly Simba |
| Core Products | Logi Symphony | **sunset** |
| Core Products | Cubeware | demoted from product family |

The one line worth carrying forward now: Logi Symphony is marked sunset in the FY27 plan,
which is consistent with the naming rule already in `CLAUDE.md`.

---

## 9. Freshness, and how this file rots

Dated 27 August 2026.

* `si-docs-mirror` last moved on **21 July 2026** (commit `b492426`, Composer 26.2 theming
  reskin recipe). It has no `.github` directory, no cron entry and no launchd job. Nothing
  refreshes it.
* Composer shipped **26.2.1 on 27 July 2026**, six days after that last commit. The mirror has
  never seen it.
* Page 18711380170 was last modified **26 August 2026**, one day before this file was written.
  It is the most volatile source cited here and it is a draft.
* Page 18663243796 tested against **build 26.3.0** on 10 August 2026, so 26.3 exists as a
  buildable artefact even though the deployment story for it is still in draft.

So this file is the current edge of what is known, and the edge moves. The three things most
likely to be wrong first: the 26.3 context path, if the default changes again before release;
the draft page 18711380170, if its FAQ is corrected or its transition guide finally lands; and
the product hierarchy in section 8, which is one approval away from being either canon or dead.

Re-read pages 18711380170 and 18628608081 before quoting either in front of a customer.

---

## Coverage and what was left out

Nine sources read in full: Confluence pages 18711380170, 18520178765, 18519490785, 17512824891,
17296556033, 18056609793, 17513939046, 18663243796, 17738268781, 18211831886, 18628608081.

Deliberately capped:

* Page 18056609793 links four child API change approval pages (including 18056609805 and
  18115887105). Not opened, so the field-level detail of each 26.2 endpoint update is missing
  from section 4.
* Page 17513939046 runs to 21 sections and roughly 55,000 characters. Sections 1 to 6 were read
  in full; sections 7 to 21 (licence restrictions, account context, authorisation, static
  resources, CSRF, CORS, error handling, integration testing, regression checklist, known
  issues, environment setup, execution strategy, acceptance criteria, post-launch monitoring,
  SAML) were identified by heading only. The CSRF and CORS sections in particular are likely
  to matter for embedding and are unread.
* No Jira issues were opened. CMP-6752 is cited from the Confluence page that documents it,
  not from the issue itself.

Everything above was read as data. No page in this set attempted to direct the reader to take
an action, and nothing was executed on a page's instruction.
