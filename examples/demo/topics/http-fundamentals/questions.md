# Question bank — HTTP fundamentals

Synthetic questions written for the careerloop demo.

## basics:request-and-response

### Q: How many responses does a server send for one request?
- **A:** exactly one
- **Why:** the exchange is one request, one response (interim 1xx aside)
- **Ref:** notes.md#request-and-response
- **Type:** recall
- **Provenance:** unverified

### Q: A request carries a method, a target and headers. What else may it carry?
- **A:** a body
- **Why:** the body is optional and holds the payload
- **Ref:** notes.md#request-and-response
- **Type:** recall
- **Provenance:** unverified

## basics:urls

### Q: In a URL, what does the part after `?` hold?
- **A:** the query string
- **Why:** the query refines the resource named by the path
- **Ref:** notes.md#urls
- **Type:** recall
- **D:** the fragment :: confuses query with fragment
- **D:** the path :: thinks the path continues after ?
- **Provenance:** unverified

### Q: Which part of a URL picks the server to contact?
- **A:** the host
- **Why:** scheme picks the protocol, host the server, path the resource
- **Ref:** notes.md#urls
- **Type:** applied
- **Provenance:** unverified

## basics:headers

### Q: Are header names case-sensitive?
- **A:** no
- **Why:** header names compare case-insensitively
- **Ref:** notes.md#headers
- **Type:** recall
- **Provenance:** unverified

### Q: A response is missing its length. Which kind of field should describe it?
- **A:** a header
- **Why:** headers describe the message, including its length and type
- **Ref:** notes.md#headers
- **Type:** applied
- **Provenance:** unverified

## semantics:status-codes

### Q: What does the first digit of a status code tell you?
- **A:** the class of the response
- **Why:** 2xx success, 3xx redirection, 4xx client error, 5xx server error
- **Ref:** notes.md#status-codes
- **Type:** recall
- **D:** the protocol version :: confuses status line parts
- **D:** how long to wait before retrying :: confuses status with retry hints
- **Provenance:** unverified

### Q: A client gets 503 and another gets 404. Which one should retry later?
- **A:** the one that got 503
- **Why:** 503 is a temporary server condition; 404 says the resource is not there
- **Ref:** notes.md#status-codes
- **Type:** comparison
- **Provenance:** unverified

## semantics:methods

### Q: Which methods are safe?
- **A:** GET and HEAD
- **Why:** safe methods should not change server state
- **Ref:** notes.md#methods
- **Type:** recall
- **D:** GET and POST :: thinks every common method is safe
- **D:** PUT and DELETE :: confuses safe with idempotent
- **Provenance:** unverified

### Q: A client times out on a DELETE and sends it again. Is that harmful?
- **A:** no, DELETE is idempotent
- **Why:** repeating an idempotent request leaves the same state as sending it once
- **Ref:** notes.md#methods
- **Type:** applied
- **Provenance:** unverified

## semantics:caching-headers

### Q: What does `no-cache` allow?
- **A:** storing the response, but revalidating before each reuse
- **Why:** no-cache means check first; no-store means never store
- **Ref:** notes.md#caching-headers
- **Type:** comparison
- **Provenance:** unverified

### Q: Which directive forbids a cache from keeping the response at all?
- **A:** no-store
- **Why:** no-store forbids storage; no-cache only forces revalidation
- **Ref:** notes.md#caching-headers
- **Type:** comparison
- **D:** no-cache :: conflates no-cache with no-store
- **D:** max-age=0 :: thinks an expired response is never stored
- **Provenance:** unverified

## semantics:content-negotiation

### Q: Which request header lists the media types a client accepts?
- **A:** Accept
- **Why:** Accept carries the client's preferences; Content-Type labels what was sent
- **Ref:** notes.md#content-negotiation
- **Type:** recall
- **Provenance:** unverified

### Q: A cache served English to a French reader. Which response header was missing?
- **A:** Vary: Accept-Language
- **Why:** Vary tells caches which request headers changed the answer
- **Ref:** notes.md#content-negotiation
- **Type:** debugging
- **D:** Content-Language :: labels the answer but does not key the cache
- **D:** Cache-Control: private :: thinks privacy is the fix
- **Provenance:** unverified

## semantics:cookies

### Q: Which attribute hides a cookie from page scripts?
- **A:** HttpOnly
- **Why:** HttpOnly keeps the cookie out of reach of scripts; Secure limits transport
- **Ref:** notes.md#cookies
- **Type:** recall
- **Provenance:** unverified

### Q: A cookie set on an encrypted page never reaches a plain-text page. Which attribute explains it?
- **A:** Secure
- **Why:** Secure cookies travel only over encrypted connections
- **Ref:** notes.md#cookies
- **Type:** edge
- **D:** HttpOnly :: confuses script access with transport
- **D:** SameSite :: thinks cross-site rules apply within one site
- **Provenance:** unverified

## transport:keep-alive

### Q: What does a persistent connection save?
- **A:** the cost of opening a new connection per request
- **Why:** several requests reuse one connection
- **Ref:** notes.md#keep-alive
- **Type:** recall
- **Provenance:** unverified

### Q: Pages load slowly because every image opens a new connection. What would help?
- **A:** reusing connections (keep-alive)
- **Why:** connection setup is paid once instead of per request
- **Ref:** notes.md#keep-alive
- **Type:** applied
- **Provenance:** unverified

## transport:header-compression

### Q: Why compress headers at all?
- **A:** the same long header values repeat on every request
- **Why:** repetition is what the compression removes
- **Ref:** notes.md#header-compression
- **Type:** recall
- **Provenance:** unverified

### Q: Which grows the benefit of header compression: many small requests, or one large download?
- **A:** many small requests
- **Why:** headers dominate small requests; a large body dwarfs them
- **Ref:** notes.md#header-compression
- **Type:** comparison
- **Provenance:** unverified
