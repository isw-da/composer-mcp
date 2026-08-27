# Security and compliance answers for Logi Composer

Provenance: absorbed from Peter Armstrong's material, 27 August 2026, from
`/Users/aminhasan/logi-composer/peter-kb/delivered-2026-08-27/Prospect-Requirement-Responses.md`
(1,196 lines, 26 requirements, all datestamped 2026-08-26).

## Citation shorthand used below

| Shorthand | File |
|---|---|
| `Peter :N` | the source path above, line N |
| `Playbook :N` | `/Users/aminhasan/logi-composer/peter-kb/delivered-2026-08-27/Prospect-Requirement-Responses-PLAYBOOK.md`, line N |
| `SBP :N` | `/Users/aminhasan/si-docs-mirror/simba-intelligence/pages/simba-intelligence/docs/reference/supplementary-resources/Security-Best-Practices.md` (2,177 lines), line N |
| `v25 security :N` | `/Users/aminhasan/si-docs-mirror/logi-composer-current/v25/articles/introduction-to-composer-25/34933064811405-security.md`, line N |
| `v25 kerberos :N` | `/Users/aminhasan/si-docs-mirror/logi-composer-current/v25/articles/manage-composer-25/34933139627149-configure-kerberos-single-sign-on-sso-settings.md`, line N |

## What this file is, and what the gap actually was

The gap between Peter's bundle and this workspace is a drafting gap, not a
knowledge gap. Seven of the topics an earlier pass called absent are documented
here already, as product documentation rather than as answers: secrets
management (`SBP :778`), data encryption (`SBP :944`), security monitoring
(`SBP :1060`), compliance and audit (`SBP :1152`), regulatory compliance
(`SBP :1842`), MFA configuration (`SBP :100`), and penetration testing
(`SBP :1563`, `SBP :2169`). Backup sits in
`/Users/aminhasan/si-docs-mirror/simba-intelligence/pages/simba-intelligence/docs/deployment/operations-and-maintenance/Backup-and-Recovery.md`
(74 lines).

What Peter added is the conversion: each requirement read for intent, answered
in a form a prospect can score, with the caveat that keeps the answer honest
attached to it. That conversion is the thing worth absorbing.

**One caveat on the `SBP` pointers.** Security-Best-Practices.md is Simba
Intelligence documentation, not Composer documentation. Its deployment-layer
guidance (Kubernetes secrets, Vault backends at `SBP :822`, KMS, monitoring)
carries across because SI and Composer share the Helm delivery model, but it is
not evidence about Composer's own application-layer behaviour. Do not cite it
as a Composer control.

## Two corrections to carry before any reuse

**Product name.** Peter's document says "Logi Symphony" 20 times, including the
subtitle at `Peter :3`. The current product is Logi Composer. Any text lifted
from that document needs a name pass first. The convention is set in
`/Users/aminhasan/logi-composer/CLAUDE.md`: Confluence and ICP files still carry
the old name and should not be allowed to propagate it.

**"Not SaaS".** Peter states flatly that Composer is self-hosted and not SaaS
(`Peter :45`, `Playbook :83`), and leans on it in eleven answers. It is a
commercial SKU statement dressed as an architectural fact, and his own text
concedes the point twice: `Peter :46` allows that Symphony may be sold in hosted
arrangements, and most of his public citations resolve to a vendor-hosted
playground at `playground.logi-symphony.com`. Phrase it as **not offered as a
vendor-managed SaaS SKU**. Everything the claim is load-bearing for stays true
under that phrasing: no vendor-held backups (`Peter :882`), no standing vendor
support access (`Peter :1019`), no vendor SOC watching the customer's instance
(`Peter :940`).

## The complete auth-mode inventory

Peter's list, stated at `Peter :485` and repeated at `:505`, `:711` and `:721`:

| Mode | Role |
|---|---|
| Trusted Access | the native embed path, client-credential minted, not an open standard |
| SAML2 | platform SSO, group and attribute mapping |
| OAuth2 / OIDC | platform SSO, and his stated fallback when literal JWT validation is required |
| X.509 | certificate authentication |
| **Kerberos** (SPNEGO) | enterprise ticket-based SSO, pairs with LDAP for group lookup |
| LDAP | directory authentication, group lookup, autoprovisioning |

His public citation is at `Peter :510`.

Two things this workspace can add that his document does not carry.

**Kerberos is mutually exclusive with SAML and X.509.** The v25 article states
that if SAML or x509 authentication is enabled you have to disable them before
enabling Kerberos SSO (`v25 kerberos :60`). Peter's inventory reads as a flat
list of six coexisting options, which will mislead anyone planning a mixed
estate. This constraint is the single most useful correction in the file.

**OAuth2 as platform SSO is weaker than his list implies.** The v25 security
overview in this mirror names Kerberos (SPNEGO), X.509 and SAML2 for single
sign-on, plus plug-ins for LDAP and SAML2 identity providers (`v25 security
:22`). It does not name OAuth2 or OIDC. In the whole v25 mirror, OAuth 2.0
appears only as a data-source connector option, for example on the BigQuery
connector. Peter's own corroboration for OIDC comes from internal tickets
(`Peter :862`), which are internal tier and cannot go to a prospect. This
matters because his Requirement 11 fallback (`Peter :498`, `Peter :503`) sends
anyone who needs literal JWT validation to the OAuth2/OIDC path. Confirm that
path with product before offering it, and say so plainly rather than repeating
the six-item list unqualified.

## Trusted Access versus JWT validation

The distinction recurs whenever a prospect names a token standard, and getting
it wrong promises something the product does not do.

**What Trusted Access is** (`Peter :481`). The parent application registers as a
client and gets a client ID and secret. When a user opens an embedded
component, the parent's backend calls the token API authenticating with those
credentials over HTTP Basic auth, asserting the user's username, account,
groups and attributes. Composer returns a short-lived encrypted user access
token, ten minutes or less, that the embed uses.

**What it is not** (`Peter :478`, `Peter :498`). Composer does not take a JWT
minted by the prospect's portal and validate its signature. It authenticates
the parent application and trusts the user context that application asserts.

**Why the distinction is worth stating rather than glossing.** The Trusted
Access token comes back with authorisation already resolved, so privileges,
object permissions, security filters and interpolated attributes are baked in
and the portal never has to encode Composer's permission model into claims
(`Peter :488`). Trust is one registered client secret rather than JWKS
plumbing, key rotation and issuer or audience configuration (`Peter :489`).

**The honest trade-off** (`Peter :495`). Trusted Access needs a server-side
call, so the token cannot be minted client-side, and it is an insightsoftware
mechanism rather than an open standard. An organisation with a mature identity
provider that mandates standards-based federation will want the OIDC path, and
the caution in the section above applies to it.

**What this workspace already holds.** The push and pull token flow, the Basic
auth header shape and the client registration constraint are documented in
`/Users/aminhasan/composer-mcp-parity/EMBEDDING.md` (lines 53 and 82) and
`/Users/aminhasan/composer-mcp-parity/SCHEMA_NOTES.md:21`. Those are empirical
notes against a live v25 instance. Peter's contribution is the positioning, not
the mechanics.

## Encryption and key management

The requirement (`Peter :613`) is deliberately comprehensive: everything
persisted, cached, replicated or backed up must be encrypted at rest, with keys
access-controlled, rotated regularly and protected. Peter's answer splits it,
and the split is the reusable part.

**Application layer, native** (`Peter :622`). Composer encrypts the sensitive
values it stores in metadata: connection parameters, secured user attributes,
and Trusted Access and OAuth tokens. The mode is configurable AES. An
administrator can supply an AES-256 JCEKS keystore for data-source credentials.
Sensitive configuration property values are encrypted with the Spring Cloud
`{cipher}` mechanism under a per-file encrypt key.

**Infrastructure layer, customer-operated** (`Peter :628`). Blanket coverage of
the metadata database, the query-result cache, uploads and backups is delivered
by database transparent data encryption, encrypted volumes, encrypted backups
and the customer's KMS. `SBP :944` is the local counterpart for the
deployment-layer half, and `SBP :778` and `SBP :822` cover secret storage and a
Vault backend.

**What to say about key management, precisely.** Application keys live in the
admin-supplied keystore and the Spring encrypt key, protected by keystore
passwords and file-system access control. Enterprise **key management** in the
sense the requirement means, meaning access-controlled, auditable and rotatable
keys, lands at the infrastructure layer in the customer's KMS or HSM.

Three things Peter flags as unconfirmed, and they should stay unconfirmed here:

- Automated or scheduled rotation of the application-layer key is not a
  documented in-product feature (`Peter :635`). Rotation is operational, or it
  is the KMS layer's job.
- Native cloud-KMS integration for the *application* keys, as opposed to the
  storage layer, is not established (`Peter :636`).
- The cache is the trap. Query results are cached in PostgreSQL by default
  (`Peter :634`), so an answer that claims application-level encryption covers
  everything is wrong. Storage-layer encryption is what covers the cache.

**Disambiguation worth keeping.** Composer's "Keyset" feature is a data-subset
and cross-source filter, not an encryption key (`Peter :638`, `Playbook :89`).
The encryption keyset material lives in the `zoomdata-keyset` database, which
is also why a backup that omits it restores incompletely (`Peter :365`).

I have not verified the JCEKS keystore or the encryption-mode properties
against a live instance. Everything in this section is Peter's reading of the
public documentation.

## Accessibility and WCAG

This is one of the two genuine knowledge holes on this side. There is no
**WCAG**, VPAT or accessibility material anywhere in `si-docs-mirror`. I
searched and found nothing.

Peter's position (`Peter :228`, `Peter :234`):

- insightsoftware publishes a VPAT and accessibility conformance report for
  Composer, stated against **WCAG** 2.0 Level A and AA, which is the Section
  508 basis.
- The VPAT covers the embedded viewing experience, not the authoring tools, and
  because Composer is a development platform a customer can build
  non-conformant features on top of it (`Peter :237`).
- **WCAG** 2.1 conformance is not confirmed. Do not claim it without a current
  VPAT that says so.
- Charts render on Canvas via ECharts, so a screen reader cannot traverse
  individual data points. The chrome around the charts is HTML. The accessible
  data path is the data table and the CSV or XLSX export (`Peter :235`).
- There is an open backlog of keyboard and focus defects, mostly in the
  authoring and admin surfaces, so "full keyboard navigation" is not a safe
  claim (`Peter :236`).

One internal inconsistency to note. `Peter :121` and `Peter :235` disagree with
`Peter :258` about whether the front end uses SVG at all: the later correction
establishes that it uses both SVG and Canvas, and that an earlier blanket "not
SVG" claim was wrong. Use the `Peter :258` version.

## Condensed answer index

Peter gives every requirement a brief answer meant to drop into a
questionnaire, and a verbose answer that banks the architecture and the
caveats. `Playbook :45` sets that split as mandatory. The brief is the
customer-facing artefact; the verbose is the durable one, and the caveats live
there.

| # | Topic | Peter | Position in one line | Local product doc |
|---|---|---|---|---|
| 1 | Embedding methods | :63 | Native JS/TS Embed Manager, no iframes, no Web Components, no per-framework SDK | `EMBEDDING.md` |
| 2 | Rendering engine | :105 | SVG plus Canvas via ECharts, WebGL unconfirmed | none |
| 3 | Client footprint | :137 | Thin loader, runtime lazily loaded, bundle optimisation still open | `EMBEDDING.md` |
| 4 | Version control and CI/CD | :171 | JSON export and import via REST, no YAML, no shipped Git or pipeline tooling | `README.md` |
| 5 | Accessibility | :217 | VPAT at WCAG 2.0 A/AA, 2.1 unconfirmed, Canvas limits in-chart screen-reader access | none, genuine hole |
| 6 | Open standards | :262 | ECharts, D3, Java/Spring, PostgreSQL, OpenAPI, JSON content. Matplotlib not applicable | none |
| 7 | Compute granularity | :300 | Per-service replicas and limits via Helm, HPA autoscaling, default max 3 replicas is licence-gated | none |
| 8 | Backup and restore | :343 | `pg_dump` of four databases plus the file-store volume, selective restore by JSON re-import | `Backup-and-Recovery.md` |
| 9 | Report monitoring and metadata | :383 | User Auditing to queryable tables plus REST metadata, no turnkey usage dashboard | `SBP :1060` |
| 10 | Pipeline utilisation | :427 | Query-serving signals only, push-down means volume lives in the data platform, no rows or bytes meter | `SBP :1060` |
| 11 | JWT and RLS | :467 | Trusted Access plus interpolated security filters. See the distinction section above | `EMBEDDING.md`, `SCHEMA_NOTES.md:21` |
| 12 | Active users and load | :518 | Derivable from audit timestamps, sessions approximated by a database view, load is a correlation | `SBP :1060` |
| 13 | Cluster and service status | :561 | Service Monitor, Consul, health endpoints, Supervisor view, Kubernetes probes. No vendor status page | none |
| 14 | Encryption at rest and keys | :608 | App-layer AES for sensitive metadata, infrastructure layer for the rest. See above | `SBP :944`, `SBP :778` |
| 15 | Data Mesh and data products | :657 | Clear no. Composer is the consumption plane, not the mesh | none, genuine hole |
| 16 | RBAC and ABAC | :700 | Groups, object ACLs, functional privileges, secure attributes to RLS and CLS, multi-tenancy | `v25 security :22` |
| 17 | Encryption in transit | :747 | Browser to server TLS with JKS or PKCS12, optional mTLS, per-connector TLS. Inter-service TLS is deployment-layer | `SBP :944` |
| 18 | MFA | :788 | Delivered by the identity provider, no native OTP for local accounts | `SBP :100` |
| 19 | Microsoft Entra ID | :826 | SAML2 or OIDC, group claims to RBAC, Entra conditional access applies | none in this mirror, see below |
| 20 | Backup location | :868 | Customer custody entirely, no vendor-side repository | `Backup-and-Recovery.md` |
| 21 | Security monitoring | :913 | Split vendor programme from customer deployment. Vendor tool names are internal tier | `SBP :1060` |
| 22 | Test and production separation | :961 | Independent deployments per environment, promotion by JSON import and export | none |
| 23 | Support authorisation | :1005 | No standing vendor access, in-product roles composed from groups and privileges | `SBP :1152` |
| 24 | Penetration testing | :1050 | Annual independent third-party test evidenced under SOC 2 Type 2, plus continuous scanning | `SBP :1563`, `SBP :2169` |
| 25 | Secrets management | :1094 | AES-256 keystore, Spring `{cipher}`, Kubernetes secrets sourced from the customer's vault | `SBP :778`, `SBP :822` |
| 26 | Deployment and DevOps | :1141 | Helm is the native IaC, headless install, air-gap supported, external PostgreSQL. No Terraform module shipped | `SBP :822` |

**Requirement 19 correction.** An earlier pass recorded Entra ID as covered in
`Multi-Tenancy-Guide.md` and `Administrator-Guide.md`. It is not. A
case-insensitive search for "entra" matches inside "cEntRAlized" and the Vertex
region "us-cEntRAl1", which is what produced those hits. A word-boundary search
for Entra ID, Microsoft Entra or Azure AD returns nothing anywhere in
`si-docs-mirror`. `Administrator-Guide.md:340` names SAML, OIDC and LDAP as
identity-provider options generically, which is the closest local coverage.
Entra ID by name is Peter's alone.

## The caveat that has to travel with every answer

Disabling Trusted Access removes row-level security in a multi-tenant
deployment. Data is then fetched with the tenant admin's credentials, so RLS
collapses silently. Peter flags it four times (`Peter :483`, `:499`, `:505`,
`:726`) and `Playbook :98` promotes it to a standing product truth.

The v25 article in this mirror documents the toggle and what breaks
functionally when it is off, meaning the client and token endpoints start
returning 404 or 401, but it does not state the security consequence
(`/Users/aminhasan/si-docs-mirror/logi-composer-current/v25/articles/composer-25-developer-tools/34933167858445-enable-trusted-access.md`,
lines 18 to 30). Peter's caveat is the more useful of the two. Attach it to any
answer about row-level security, multi-tenancy or embedded authorisation.

## Genuine knowledge holes

Two, and only two.

**WCAG 2.1.** No accessibility material of any kind on this side. The VPAT
itself is NDA tier and has to come through the account or security team, so the
hole cannot be closed by reading more documentation. See `DISCLOSURE.md`.

**Data Mesh.** Nothing in `si-docs-mirror`, nothing in `composer-vs-legacy`,
nothing here. Peter's answer is a clear no (`Peter :668`), positioning Composer
as the consumption plane on top of a mesh rather than the mesh. `Playbook :116`
makes the general point that a clear no is fine when it is true. The one thing
to carry across is the disambiguation at `Peter :681`: Composer's front end uses
Blueprint.js, the React component library, which has nothing to do with
Blueprint-driven data-product configuration. Citing it as a match would be a
serious misread.

## Defects in the source document

Structural, and they will confuse anyone reading it cold.

**Requirement 2 has no sources block.** The heading map runs `## Requirement 2`
at `:105` straight through to `## Requirement 3` at `:137` with no `### (4)
Sources`.

**Requirement 5 has two.** The first, at `:243` to `:249`, is genuinely
Requirement 5's: VPAT, accessibility defects, the WCAG name-tag tracker. The
second, at `:251` to `:258`, is about custom charting libraries, the Zoomdata
Frontend page and visual architecture, which is Requirement 2's subject matter.
It is Requirement 2's orphaned block, filed one section too late. Its
verification note at `:258` carries the SVG-plus-Canvas correction, which is
why it matters that it is easy to miss.

**Line counts.** `SECURITY_ANSWERS.md` and `DISCLOSURE.md` are the only two
files this node writes. Nothing else in `composer-mcp-parity` was touched.
