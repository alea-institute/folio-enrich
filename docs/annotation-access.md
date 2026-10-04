# Proposition annotation access

Cloudflare Access is the primary sign-in method for deployed proposition
annotation. Open the plain Propositions link and sign in with an allowed email.
The toolbar shows **Signed in as <email> (Cloudflare Access)** after the origin
verifies the login. Annotation access codes remain available under **Session
tools** as a break-glass fallback.

## Configure Cloudflare Access

Configure the Cloudflare Access application and identity provider for the
instance, then set these environment variables on that instance:

```text
FOLIO_ENRICH_CF_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
FOLIO_ENRICH_CF_ACCESS_AUD=your-access-application-audience
FOLIO_ENRICH_CF_ACCESS_ALLOWED_EMAILS=annotator@example.com,reviewer@example.com
```

The email allow-list is comma-separated and matched case-insensitively. Access
is enabled only when all three settings are set. The current rollout is DEV
only; configuring DEV does not change the propositions PROD instance.

The origin verifies `Cf-Access-Jwt-Assertion` using the team's published JWKS
at `https://<team>/cdn-cgi/access/certs`. It accepts only RS256 and checks the
signature, issuer, application audience, expiration, and allowed email. The
header's presence alone grants no access. JWKS fetch failures deny access.
Access-authorized mutations also require the request `Origin` to match its
`Host`, preventing sibling-domain CSRF. Requests to a fallback hostname or bare
IP without a valid Access assertion require a break-glass token.

`GET /gold/access` reports `authenticated`, `via` (`cloudflare-access`, `token`,
`open`, or `null`), and `email` (only for Access sign-in). It never returns a
credential. With Access disabled, the existing annotation and admin token
behavior remains unchanged. Gold mutations are open for local/trusted
development only when Access and both tokens are unconfigured.

## Configure a break-glass token

Set a unique random value on each instance:

```sh
openssl rand -hex 32
```

Store that value as `FOLIO_ENRICH_ANNOTATION_TOKEN` in the instance environment.
Keep `FOLIO_ENRICH_ADMIN_TOKEN` separate. The annotation token authorizes only
mutating `/gold` routes; it cannot authorize ontology updates or other admin
operations. The admin token also continues to authorize gold mutations.

## Create a break-glass Remote Control link

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
Clearing the token cookie does not sign you out of Cloudflare Access.

Use a different token for DEV and PROD. Rotate either token by changing the
corresponding environment value and recreating only that instance. Previously
issued links then stop authorizing writes after the container restart.
