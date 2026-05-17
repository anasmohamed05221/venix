# Auth API Contract

This document defines the API contract for authentication-related endpoints in the MVP version of the E-Commerce backend.

---

# 1. Register

## Request

**POST** `/auth/`

Rate limit: 3/minute

Request body:

{
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "Secret123",
  "phone_number": "+201234567890"
}

## Validation Rules

- `email`: must be a valid email address.
- `password`: min 8 characters, must contain at least one letter and one digit.
- `phone_number`: must be a valid international phone number (E.164 format, e.g. `+201234567890`).

---

## Response (201 Created)

{
  "message": "Registration successful. A verification email will be sent to your inbox shortly. If you don't receive it, you can request a new one."
}

---

## Notes

- A 6-digit email verification code is dispatched asynchronously after registration. It may take a few moments to arrive.
- The account cannot be used until the email is verified.
- If the email does not arrive, use `POST /auth/resend-verification` to request a new code.

---

## Errors

- `422 Unprocessable Entity` — validation rule violations.
- `429 Too Many Requests` — rate limit exceeded.

---

# 2. Login

## Request

**POST** `/auth/token`

Rate limit: 5/minute

Form data (OAuth2 password flow):

- `username` (string, required) — the user's email address.
- `password` (string, required).

---

## Response (200 OK)

{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "token_type": "bearer"
}

---

## Notes

- `access_token` is a short-lived JWT used in `Authorization: Bearer <token>` headers.
- `refresh_token` is a long-lived opaque token used to obtain new access tokens.
- Returns `401` if the account is not verified or not active.

---

## Errors

- `401 Unauthorized` — incorrect credentials, unverified account, or inactive account.
- `422 Unprocessable Entity` — missing form fields.
- `429 Too Many Requests` — rate limit exceeded.

---

# 3. Verify Email

## Request

**POST** `/auth/verify`

Rate limit: 3/minute

Request body:

{
  "email": "user@example.com",
  "code": "483921"
}

## Validation Rules

- `code`: must be exactly 6 characters.

---

## Response (200 OK)

{
  "message": "Email verified successfully"
}

---

## Errors

- `400 Bad Request` — user not found, already verified, code mismatch, or code expired.
- `422 Unprocessable Entity` — code is not 6 characters.
- `429 Too Many Requests` — rate limit exceeded.

---

# 4. Refresh Token

## Request

**POST** `/auth/refresh`

Rate limit: 10/minute

Request body:

{
  "refresh_token": "<opaque>"
}

---

## Response (200 OK)

{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "token_type": "bearer"
}

---

## Errors

- `401 Unauthorized` — invalid or expired refresh token.
- `422 Unprocessable Entity` — refresh token is empty.
- `429 Too Many Requests` — rate limit exceeded.

---

# 5. Logout

## Request

**POST** `/auth/logout`

Rate limit: 10/minute

Request body:

{
  "refresh_token": "<opaque>"
}

---

## Response (200 OK)

{
  "message": "Logged out successfully"
}

---

## Notes

- Revokes the provided refresh token. The access token remains valid until it naturally expires.

---

## Errors

- `422 Unprocessable Entity` — refresh token is empty.
- `429 Too Many Requests` — rate limit exceeded.

---

# 6. Forgot Password

## Request

**POST** `/auth/forgot-password`

Rate limit: 3/minute

Request body:

{
  "email": "user@example.com"
}

---

## Response (200 OK)

{
  "message": "If that email exists, a reset link has been sent."
}

---

## Notes

- Always returns the same message regardless of whether the email exists (prevents email enumeration).
- A password reset link is sent via email if the account exists.
- The reset token expires in 15 minutes.

---

## Errors

- `429 Too Many Requests` — rate limit exceeded.

---

# 7. Reset Password

## Request

**POST** `/auth/reset-password`

Rate limit: 5/minute

Request body:

{
  "token": "<reset_token>",
  "new_password": "NewSecret123"
}

## Validation Rules

- `new_password`: min 8 characters, must contain at least one letter and one digit.

---

## Response (200 OK)

{
  "message": "Password updated successfully. Please login again."
}

---

## Notes

- The reset token is extracted from the link sent to the user's email.
- On success, all active refresh tokens for the user are revoked (forces re-login on all devices).

---

## Errors

- `400 Bad Request` — invalid or expired reset token.
- `422 Unprocessable Entity` — password validation failure.
- `429 Too Many Requests` — rate limit exceeded.

---

# 8. Resend Verification Email

## Request

**POST** `/auth/resend-verification`

Rate limit: 3/minute

Request body:

{
  "email": "user@example.com"
}

---

## Response (200 OK)

{
  "message": "If your email is registered and unverified, a new verification code has been sent."
}

---

## Notes

- Always returns the same message regardless of whether the email exists (prevents user enumeration).
- Generates a fresh code and invalidates the previous one.
- If the account is already verified, this is a no-op.

---

## Errors

- `429 Too Many Requests` — rate limit exceeded.
