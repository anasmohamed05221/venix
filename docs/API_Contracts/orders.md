# Orders API Contract

This document defines the API contract for order-related endpoints in the MVP version of the E-Commerce backend.

---

# 1. Checkout (Create Order)

## Request

**POST** `/orders/`

Rate limit: 5/minute

- Requires `Authorization: Bearer <access_token>`.

Request body:

{
  "address_id": 1,
  "payment_method": "cod"   // or "stripe"
}

## Validation Rules

- `address_id`: required, must be an address belonging to the current user.
- `payment_method`: required, must be `"cod"` or `"stripe"`.

---

## Response (201 Created)

**COD example:**

{
  "id": 7,
  "total_amount": 1050.00,
  "status": "pending",
  "payment_status": "unpaid",
  "payment_method": "cod",
  "checkout_url": null,
  "items": [
    {
      "id": 1,
      "product": {
        "id": 3,
        "name": "Laptop",
        "price": 1000.00,
        "image_url": "..."
      },
      "price_at_time": 1000.00,
      "quantity": 1,
      "subtotal": 1000.00
    }
  ],
  "created_at": "2026-04-12T10:00:00",
  "updated_at": "2026-04-12T10:00:00"
}

**Stripe example:**

{
  "id": 8,
  "total_amount": 1050.00,
  "status": "pending",
  "payment_status": "unpaid",
  "payment_method": "stripe",
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_...",
  "items": [...],
  "created_at": "2026-04-12T10:00:00",
  "updated_at": "2026-04-12T10:00:00"
}

---

## Notes

- The cart must be non-empty.
- `address_id` must belong to the authenticated user.
- **COD path:** stock is decremented and cart is cleared atomically at checkout. `checkout_url` is null.
- **Stripe path:** stock is NOT decremented at checkout. A Stripe Checkout Session is created and `checkout_url` is returned. The user completes payment on Stripe's hosted page. Stock is decremented only when the webhook confirms payment (SCRUM-120).
- **Reuse-if-valid:** if the user already has an UNPAID Stripe order with an open session, the existing `checkout_url` is returned without creating a new order or session.
- Stock is validated before and after acquiring a row-level lock (pessimistic locking / SELECT FOR UPDATE) on the COD path.
- `price_at_time` reflects the product price at moment of purchase (price snapshot).

---

## Errors

- `400 Bad Request` — cart is empty.
- `401 Unauthorized` — missing or invalid token.
- `404 Not Found` — address not found or belongs to another user.
- `409 Conflict` — insufficient stock for one or more items (COD path only).
- `422 Unprocessable Entity` — missing required fields or invalid payment_method.
- `429 Too Many Requests` — rate limit exceeded.
- `502 Bad Gateway` — Stripe API unavailable. Order is marked FAILED; no stock is decremented.

---

# 2. List Orders

## Request

**GET** `/orders/`

## Query Parameters (all optional)

- `limit` (int, default `10`, min `1`, max `50`)
- `offset` (int, default `0`, min `0`)

## Validation Rules

- `limit` must be between 1 and 50.
- `offset` must be ≥ 0.

---

## Response (200 OK)

Example:

{
  "items": [
    {
      "id": 1,
      "total_amount": 1050.00,
      "status": "pending",
      "created_at": "2026-03-30T10:00:00"
    }
  ],
  "limit": 10,
  "offset": 0,
  "total": 1
}

---

## Response Fields

- `items`: list of order summary objects.
- `limit`: number of items requested.
- `offset`: number of items skipped.
- `total`: total number of orders for the current user (used for pagination UI).

---

## Notes

- Returns only orders belonging to the authenticated user.
- Orders are returned newest first (ordered by `created_at DESC`).
- An empty list returns `200 OK` with `items: []`, not `404`.

---

## Errors

- `401 Unauthorized` — user is not authenticated.
- `422 Unprocessable Entity` — invalid query parameter types or validation rule violations.

---

# 2. Order Detail

## Request

**GET** `/orders/{order_id}`

- `order_id` (int, required, path parameter)

---

## Response (200 OK)

Example:

{
  "id": 1,
  "total_amount": 1050.00,
  "status": "pending",
  "payment_status": "unpaid",
  "payment_method": "cod",
  "checkout_url": null,
  "items": [
    {
      "id": 1,
      "product": {
        "id": 3,
        "name": "Laptop",
        "price": 1000.00,
        "image_url": "..."
      },
      "price_at_time": 1000.00,
      "quantity": 1,
      "subtotal": 1000.00
    }
  ],
  "created_at": "2026-03-30T10:00:00",
  "updated_at": "2026-03-30T10:00:00"
}

---

## Notes

- Ownership is enforced: a user can only view their own orders.
- `price_at_time` reflects the product price at the moment of purchase (price snapshot), not the current product price.
- Items include full product details.

---

## Errors

- `401 Unauthorized` — user is not authenticated.
- `404 Not Found` — order does not exist or belongs to another user.

---

# 3. Cancel Order

## Request

**POST** `/orders/{order_id}/cancel`

- `order_id` (int, required, path parameter)
- No request body.

---

## Response (200 OK)

Returns the updated order in full `OrderOut` format (same as Order Detail response above), with `status` set to `"cancelled"`.

---

## Notes

- Only orders with status `PENDING` can be cancelled.
- On successful cancellation:
  - Order status is set to `CANCELLED`.
  - Stock is restored for each order item.
  - An `InventoryChange` record is logged per item with `reason="cancellation"`.
  - The entire operation is atomic — if any step fails, the whole transaction rolls back.
- Ownership is enforced: a user can only cancel their own orders.
- Concurrent cancel requests on the same order are safe: pessimistic locking ensures only one succeeds.

---

## Order Status Lifecycle

Valid order statuses and transitions (FSM):

- `pending` → `confirmed` (admin)
- `confirmed` → `shipped` (admin)
- `shipped` → `completed` (admin)
- Any non-terminal status → `cancelled` (customer: pending only; admin: pending or confirmed)

---

## Errors

- `401 Unauthorized` — user is not authenticated.
- `404 Not Found` — order does not exist or belongs to another user.
- `409 Conflict` — order is not in `PENDING` status (already cancelled, completed, etc.).
