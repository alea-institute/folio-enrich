# Proposition annotation access

Deployed proposition annotation uses a credential that is separate from the
general FOLIO Enrich admin token.

## Configure an instance

Set a unique random value on each instance:

```sh
openssl rand -hex 32
```

Store that value as `FOLIO_ENRICH_ANNOTATION_TOKEN` in the instance environment.
Keep `FOLIO_ENRICH_ADMIN_TOKEN` separate. The annotation token authorizes only
mutating `/gold` routes; it cannot authorize ontology updates or other admin
operations. When neither token is configured, gold mutation remains open for
local/trusted development, matching the existing local convention.

## Create a Remote Control link

Append the annotation token in the URL fragment, not the query string:

```text
https://HOST/?job=JOB_ID&tab=propositions#annotation-access=TOKEN
```

The fragment is not sent to the server or included in HTTP referrers. Before any
third-party script runs, a small first-party bootstrap removes the fragment,
exchanges the credential, and erases any legacy local-storage token. The server
returns an `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/gold`, so
scripts cannot read the credential and unrelated routes never receive it.
Cookie-authenticated mutations additionally require the request `Origin` to
match its `Host`, preventing sibling-domain CSRF even under broad legacy CORS.
Subsequent links can omit the fragment for seven days or until access is cleared.

Use a different token for DEV and PROD. Rotate either token by changing the
corresponding environment value and recreating only that instance. Previously
issued links then stop authorizing writes after the container restart.

## Long-term identity layer

Cloudflare Access remains the preferred human-authentication layer once the
Cloudflare Zero Trust organization and identity provider are initialized. The
origin must verify the signed `Cf-Access-Jwt-Assertion` issuer, audience,
expiration, and signature before accepting it; the header alone is not trusted.
The scoped annotation token is the interim mechanism and break-glass fallback.
