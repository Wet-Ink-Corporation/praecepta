# infra-auth -- Library Usage Audit

**Upstream Libraries:** PyJWT >=2.8, httpx >=0.28, bcrypt >=4.0
**RAG Status:** AMBER
**Checklist:** 13/17 passed

## Findings

| ID | Severity | Checklist | Description | File:Line | Recommendation |
|----|----------|-----------|-------------|-----------|----------------|
| F-01 | HIGH | AU-4 FAIL | `OIDCTokenClient` creates a new `httpx.AsyncClient` per method call (`async with httpx.AsyncClient() as client`). Three separate instantiation sites in `_token_request` and `revoke_token`. While the docstring acknowledges this is intentional for infrequent calls, each instantiation performs a fresh TLS handshake and TCP connection setup. Under token refresh storms or bulk revocation this becomes an N+1 resource multiplication anti-pattern. | `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py:149,185` | Inject a shared `httpx.AsyncClient` via constructor (lifespan-scoped singleton). Use `async with` only as fallback. This also resolves AU-14. |
| F-02 | HIGH | AU-14 FAIL | Because `httpx.AsyncClient` is created per-call via context manager, there is no persistent client to close during shutdown. However, if the design is changed to a singleton client (per F-01 recommendation), explicit shutdown cleanup via `aclose()` in a lifespan hook will be required. Currently the per-call pattern does close each client, but at the cost of connection pooling. | `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py:149,185` | When moving to singleton client, register `aclose()` in a lifespan shutdown hook. |
| F-03 | MEDIUM | AU-10 FAIL | OIDC discovery document is not fetched or validated. `JWKSProvider` constructs the JWKS URI by appending `/.well-known/jwks.json` to the issuer URL directly, rather than fetching `/.well-known/openid-configuration` and extracting the `jwks_uri` field. The issuer claim in the discovery document is not validated against the configured issuer, and HTTPS is not enforced on endpoints. | `packages/infra-auth/src/praecepta/infra/auth/jwks.py:67` | Fetch `/.well-known/openid-configuration`, validate `issuer` matches, extract `jwks_uri`, and verify all endpoints use HTTPS. Alternatively, add explicit HTTPS validation on the constructed URI. |
| F-04 | MEDIUM | AU-16 PARTIAL | `AuthSettings` does not validate `issuer` URL format (no check for HTTPS scheme, valid URL structure, or non-empty value in production). The `issuer` field defaults to empty string with no format validation. `jwks_cache_ttl` has `ge=30, le=86400` bounds, which is good. OAuth fields have `validate_oauth_config()` but issuer/JWKS URL do not. | `packages/infra-auth/src/praecepta/infra/auth/settings.py:55-58` | Add a Pydantic validator for `issuer` that enforces HTTPS scheme when not empty and when `dev_bypass` is False. Consider using `AnyHttpUrl` type or a `@field_validator`. |

## Detailed Checklist Results

### Library API Usage

| ID | Status | Evidence |
|----|--------|----------|
| AU-1 | PASS | `jwt.decode()` called with explicit `algorithms=["RS256"]` at `jwt_auth.py:192`. No fallback to HS256. |
| AU-2 | PASS | `JWKSProvider` wraps `PyJWKClient` with `cache_jwk_set=True` and configurable `lifespan=cache_ttl` (default 300s) at `jwks.py:71-75`. PyJWKClient handles kid mismatch -> refresh -> retry internally. |
| AU-3 | PASS | `_BCRYPT_ROUNDS = 12` defined at `api_key_generator.py:23`, used in `bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)` at line 108. Well above the minimum of 12. |
| AU-4 | FAIL | Per-request `httpx.AsyncClient` instantiation in `oidc_client.py:149` and `oidc_client.py:185`. No connection pooling. See F-01. |
| AU-5 | PASS | `jwt.decode()` at `jwt_auth.py:189-196` validates `issuer`, `audience`, and requires `["exp", "iss", "aud", "sub"]` via the `options={"require": [...]}` parameter. Separate exception handlers for `ExpiredSignatureError`, `InvalidIssuerError`, `InvalidAudienceError`. |
| AU-6 | PASS (N/A) | The PKCE module only provides `derive_code_challenge()` (S256 hash) and `PKCEStore` (storage). Code verifier generation is not in this package -- it is presumably handled by callers. The API key generator uses `secrets.token_urlsafe()` at `api_key_generator.py:59-60`, which is cryptographically secure. No use of `random` module found anywhere. |

### Security

| ID | Status | Evidence |
|----|--------|----------|
| AU-7 | PASS | API key verification uses `bcrypt.checkpw()` at `api_key_auth.py:196-198` and `api_key_generator.py:131`, which is inherently constant-time. No `==` comparison on key material. |
| AU-8 | PASS | JWT error responses return generic messages like "Token signature verification failed", "Token is malformed", "Token validation failed" at `jwt_auth.py:197-223`. No algorithm, key ID, or key material information is leaked. Error codes are semantic (e.g., `invalid_signature`, `invalid_token`) but not revealing. |
| AU-9 | PASS | Dev bypass requires explicit `AUTH_DEV_BYPASS=true` setting AND passes through `resolve_dev_bypass()` which checks `ENVIRONMENT` env var. Production (`ENVIRONMENT=production`) always blocks bypass at `dev_bypass.py:44`. Bypass only activates when no Authorization header is present (`jwt_auth.py:139`). |
| AU-10 | FAIL | See F-03. No OIDC discovery document fetch or validation. |
| AU-11 | PASS (Implicit) | Clock skew handling is delegated to PyJWT's built-in `leeway` parameter (defaults to 0). The `jwt.decode()` call at `jwt_auth.py:189` does not set explicit leeway, which means strict expiration. This is acceptable for most deployments but could be improved by exposing a configurable leeway setting. |
| AU-12 | PASS | `_SECRET_BYTES = 32` at `api_key_generator.py:22`, using `secrets.token_urlsafe(32)` which produces 256 bits of entropy. This meets the >= 256-bit requirement. |
| AU-13 | PASS | All auth failures return 401 with `WWW-Authenticate` header. Role-based authorization in `dependencies.py:81` raises `AuthorizationError` (which maps to 403 via error handler convention). The middleware correctly distinguishes: missing/invalid credentials = 401, insufficient permissions = AuthorizationError (403). |

### Resource Management

| ID | Status | Evidence |
|----|--------|----------|
| AU-14 | FAIL | See F-02. Per-call AsyncClient means no persistent resource to manage, but also no connection pooling benefit. |
| AU-15 | PASS | JWKS cache is managed by `PyJWKClient` with `cache_jwk_set=True` and `lifespan=cache_ttl` at `jwks.py:71-75`. PyJWKClient replaces the cached keyset on refresh rather than appending, so the cache is inherently bounded (one keyset at a time with TTL expiry). |

### Configuration

| ID | Status | Evidence |
|----|--------|----------|
| AU-16 | PARTIAL | See F-04. OAuth fields are validated via `validate_oauth_config()` but `issuer` has no format validation. `jwks_cache_ttl` has proper bounds (`ge=30, le=86400`). |
| AU-17 | PASS | `oauth_client_secret` uses `repr=False` at `settings.py:81` to prevent logging in repr output. No settings dump endpoint found. The `extra="ignore"` config prevents unknown env vars from leaking into the model. |

## Narrative

The `infra-auth` package demonstrates generally sound security practices. JWT validation correctly enforces RS256 with explicit algorithm pinning and full claims validation (exp, iss, aud, sub). Bcrypt usage is properly configured with 12 rounds and constant-time comparison. API key generation uses `secrets` for cryptographic randomness with 256-bit entropy. The dev bypass has a robust production lockout mechanism.

The primary concern is the `OIDCTokenClient` creating a new `httpx.AsyncClient` per method call (F-01/F-02). The code comments acknowledge this as intentional for "infrequent" calls, but this creates unnecessary TLS overhead and forgoes connection pooling. While OIDC token calls are indeed less frequent than JWKS lookups, a lifespan-scoped client would be a straightforward improvement with no downsides.

The lack of OIDC discovery document validation (F-03) means the JWKS URI is constructed by convention rather than verified through the standard `.well-known/openid-configuration` endpoint. This works in practice but deviates from the OIDC specification and misses the opportunity to validate that the issuer claim in the discovery document matches the configured issuer.

The `AuthSettings.issuer` field lacks format validation (F-04), which could allow misconfiguration to propagate silently. Adding a Pydantic validator that enforces HTTPS scheme when bypass is disabled would catch configuration errors early.

No anti-patterns from the projection remediation were found (no N+1 resource multiplication beyond the httpx issue, no polling-where-subscriptions-exist, no bypassing of purpose-built abstractions).
