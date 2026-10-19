# HTTP fundamentals: demo notes

Synthetic study notes written for the careerloop demo. Every question in
questions.md points at one of these anchors.

## request-and-response
A client opens a connection and sends a request: a method, a target, headers
and an optional body. The server sends back one response: a status code,
headers and an optional body.

## urls
A URL names a resource: a scheme (https), a host, an optional port, a path
and an optional query string after `?`.

## headers
Headers are name-value pairs. Names are case-insensitive. They describe the
message (length, type) and the exchange (caching, authentication).

## status-codes
The first digit is the class: 1xx informational, 2xx success, 3xx
redirection, 4xx the client's error, 5xx the server's error. 404 means the
resource was not found; 503 means the server cannot handle the request now.

## methods
GET and HEAD are safe: they should not change state. PUT and DELETE are
idempotent: sending the same request twice leaves the same state as once.
POST is neither.

## caching-headers
`Cache-Control: max-age=N` lets a cache reuse a response for N seconds.
`no-store` forbids storing it at all; `no-cache` allows storing but requires
revalidation first. `ETag` with `If-None-Match` lets a client revalidate and
receive `304 Not Modified` instead of the whole body.

## content-negotiation
A client lists what it accepts (`Accept`, `Accept-Language`); the server
picks a representation and says which with `Content-Type` and
`Content-Language`. `Vary` tells caches which request headers changed the
answer.

## cookies
A server sets a cookie with `Set-Cookie`; the client returns it in `Cookie`
on later requests to the same site. `HttpOnly` hides it from scripts;
`Secure` sends it only over encrypted connections.

## keep-alive
Persistent connections let several requests reuse one connection, saving the
cost of opening a new one for each request.

## header-compression
Newer versions of the protocol compress headers, because the same long header
values repeat on every request.
