# Public API rate limits

The Northwind Cloud REST API enforces rate limits per API key.

| Plan | Requests per minute | Burst |
|---|---|---|
| Starter | 60 | 20 |
| Business | 600 | 100 |
| Enterprise | 6,000 | 1,000 |

When a client exceeds the limit, the API answers HTTP 429 with a Retry-After header in seconds. Clients should retry with exponential backoff starting at the Retry-After value.

## Pagination

List endpoints return at most 100 items per page and use cursor pagination: pass the next_cursor value from the previous response. Offset pagination is deprecated and will be removed on 2027-03-01.

## Webhooks

Webhook deliveries are retried up to 8 times over 24 hours with exponential backoff. Each delivery carries an HMAC-SHA256 signature in the X-Northwind-Signature header.
