# HTTP fundamentals

Goal: demo (invented study topic; the Ref source is notes.md beside this file)

## Concepts

- basics :: request and response :: a client sends a request and a server answers it :: cluster:messages
- basics :: urls :: scheme, host, path and query
- basics :: headers :: metadata carried on requests and responses :: cluster:messages
- semantics :: status codes :: what the response classes mean :: cluster:responses
- semantics :: methods :: safe and idempotent methods :: cluster:responses
- semantics :: caching headers :: cache-control and validators
- semantics :: content negotiation :: how a client asks for a representation
- semantics :: cookies :: state carried between requests
- transport :: keep-alive :: reusing one connection for several requests
- transport :: header compression :: shrinking repeated headers :: scope:depth
