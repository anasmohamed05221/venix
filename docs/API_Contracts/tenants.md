# Tenants API Contract

This document defines the API contract for tenant registration and management endpoints.

---

# 1. Register Tenant

## Request

**POST** `/tenants/register`

Rate limit: 3/minute

Request body:

{
  "name": "Acme Store",
  "slug": "acme-store",
  "plan": "free"
}

## Validation Rules

- `name`: required, max 100 characters.
- `slug`: required, 3–50 characters, must match `^[a-z0-9][a-z0-9-]{2,49}$` — lowercase letters, digits, hyphens only, no leading hyphen.
- `plan`: optional, default `"free"`. Valid values: `"free"` | `"pro"` | `"enterprise"`.

---

## Response (201 Created)

{
  "id": "<uuid7>",
  "name": "Acme Store",
  "slug": "acme-store",
  "plan": "free",
  "is_active": true,
  "created_at": "<iso8601>",
  "api_key": "vnx_xKp...47chars",
  "message": "Tenant created successfully. The owner account was automatically registered as the tenant administrator and can log in to the store using the same credentials."
}

---

## Notes

- The `api_key` is shown **exactly once** in this response. It is never stored in plaintext — only a SHA256 hash is persisted. If lost, use the key rotation endpoint to issue a new one. The client is responsible for displaying an appropriate warning to the user.
- The `api_key` is always prefixed with `vnx_` for identification and secret-scanning compatibility.
- The `id` is a UUID7 — time-ordered, safe against business leakage, and compatible with distributed systems.
- The `slug` is immutable after registration and will appear in per-tenant webhook URLs.

---

## Errors

- `409 Conflict` — slug is already taken by another tenant.
- `422 Unprocessable Entity` — slug fails regex, name exceeds 100 characters, or invalid plan value.
- `429 Too Many Requests` — rate limit exceeded.

---

# 2. Rotate API Key

## Request

**POST** `/tenants/me/rotate-api-key`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 3/minute per tenant (keyed on `tenant_id`, not IP)

No request body.

## Response (200 OK)

```json
{
  "api_key": "vnx_...new key...",
  "message": "New API key issued. Save it now — it will not be shown again."
}
```

## Notes

- Rotation is atomic — old key revoked and new key written in a single transaction. No window where neither key is valid.
- The old key is immediately invalid after this call. Both `tenant:apikey:{old_hash}` and `tenant:id:{tenant_id}` Redis cache entries are deleted after commit.
- Rate limit is per-tenant to prevent key-cycling denial-of-service attacks through proxied IPs.

## Errors

- `401 Unauthorized` — no valid tenant resolved from the request.
- `429 Too Many Requests` — rate limit exceeded.

---

# 3. Revoke API Key

## Request

**DELETE** `/tenants/me/api-key`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

No request body.

## Response (200 OK)

```json
{
  "message": "API key revoked. Use your credentials to log in and rotate a new key."
}
```

## Notes

- Sets `api_key_hash = null` on the tenant row. The tenant account remains **active**.
- Any subsequent request using an API key header returns 401 — no hash is stored to match against.
- The tenant can still authenticate via JWT and call the rotate endpoint to obtain a new key.
- This is NOT account deactivation. To deactivate the account entirely, use `POST /tenants/deactivate` (Story 2.6).
- Redis cache entries for the revoked key are invalidated immediately after DB commit.

## Errors

- `401 Unauthorized` — no valid tenant resolved from the request.

---

# 4. Get Tenant Profile

## Request

**GET** `/tenants/me`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

No request body.

## Response (200 OK)

```json
{
  "id": "<uuid7>",
  "name": "Acme Store",
  "slug": "acme-store",
  "owner_email": "owner@acme.com",
  "plan": "free",
  "is_active": true,
  "is_verified": false,
  "created_at": "<iso8601>"
}
```

## Notes

- Never returns: `owner_password_hash`, `api_key_hash`, `stripe_secret_key`, `stripe_webhook_secret`, `db_url`, `password_change_code`.

## Errors

- `401 Unauthorized` — no valid tenant resolved.

---

# 5. Update Tenant Profile

## Request

**PUT** `/tenants/me`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

```json
{
  "name": "Acme Store Updated"
}
```

## Validation Rules

- `name`: optional, 1–100 characters.

## Response (200 OK)

Returns updated `TenantProfileOut` (same shape as `GET /tenants/me`).

## Notes

- `slug` is immutable — not accepted in this request body.

## Errors

- `401 Unauthorized` — no valid tenant resolved.
- `422 Unprocessable Entity` — name fails length validation.

---

# 6. Verify Email

## Request

**POST** `/tenants/me/verify-email`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 5/minute per tenant

```json
{
  "code": "847291"
}
```

## Response (200 OK)

```json
{
  "message": "Email verified successfully."
}
```

## Notes

- Code is a 6-digit numeric string, expires in 10 minutes.
- Authenticated endpoint — explicit errors (no silent no-op, no enumeration risk).
- Wrong code does NOT clear the code — it expires naturally. Rate limiting prevents brute force.

## Errors

- `400 Bad Request` — invalid code, expired code, or email already verified.
- `401 Unauthorized` — no valid tenant resolved.

---

# 7. Resend Verification Email

## Request

**POST** `/tenants/me/resend-verification`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 3/minute per tenant

No request body.

## Response (200 OK)

```json
{
  "message": "Verification email sent."
}
```

## Notes

- Regenerates code and expiry — invalidates any previous code.
- Authenticated endpoint — explicit 400 if already verified (no silent no-op).

## Errors

- `400 Bad Request` — email already verified.
- `401 Unauthorized` — no valid tenant resolved.

---

# 8. Initiate Password Change

## Request

**POST** `/tenants/me/initiate-change-password`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 3/minute per tenant

```json
{
  "current_password": "current-secret"
}
```

## Response (200 OK)

```json
{
  "message": "A confirmation code has been sent to your email."
}
```

## Notes

- Verifies `current_password` against `owner_password_hash` before sending code.
- Code is a 6-digit numeric string, expires in 15 minutes.
- Code is stored as SHA256 hash in DB — plaintext never persisted.
- Email sent from `no-reply@venix.website` (Venix platform account).

## Errors

- `401 Unauthorized` — incorrect current password, or no valid tenant resolved.

---

# 9. Change Password

## Request

**POST** `/tenants/me/change-password`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 3/minute per tenant

```json
{
  "code": "847291",
  "new_password": "new-secret-password"
}
```

## Response (200 OK)

```json
{
  "message": "Password changed successfully. All sessions have been revoked."
}
```

## Notes

- Validates code + expiry in one atomic request with the new password — no separate confirm step.
- Applies new hash to `tenant.owner_password_hash` AND syncs `User.hashed_password` for the auto-provisioned admin user (shared credential from Story 4.5).
- Revokes all admin User JWT sessions after applying the change.
- Code fields are cleared after successful change — code cannot be reused.

## Errors

- `400 Bad Request` — invalid or expired code.
- `401 Unauthorized` — no valid tenant resolved.
- `422 Unprocessable Entity` — new password fails strength validation.

---

# 10. Deactivate Account

## Request

**POST** `/tenants/deactivate`

Auth: `X-Tenant-API-Key` header or `Authorization: Bearer <jwt>`

Rate limit: 3/minute per tenant

```json
{
  "password": "current-secret"
}
```

## Response (200 OK)

```json
{
  "message": "Account deactivated."
}
```

## Notes

- Requires `is_verified=True` — unverified accounts cannot be deactivated.
- Sets `is_active=False`. All subsequent requests return 403 from the middleware.
- Invalidates both Redis cache entries (`tenant:apikey:{hash}` and `tenant:id:{uuid}`) immediately after DB commit.
- This is NOT key revocation — see `DELETE /tenants/me/api-key` (Story 2.5). Deactivation disables the entire account.
- Reactivation requires super-admin action (deferred).

## Errors

- `401 Unauthorized` — incorrect password, or no valid tenant resolved.
- `403 Forbidden` — tenant is not verified.