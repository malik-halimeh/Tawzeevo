# Authentication and session contract

Public registration always creates a `client` and never accepts an authorization role. Passwords use Argon2id. Access JWTs expire after 15 minutes and remain in memory in the operations client. Opaque refresh tokens expire after 30 days, are stored only as hashes server-side, and are delivered through an HttpOnly cookie that is Secure in production, SameSite=Lax, and scoped to `/api/v1/auth`.

Refresh tokens rotate on every refresh. Reuse of a rotated token revokes all active sessions for that user. Protected requests validate the access-token signature and claims, session state, expiry, user deletion state, and matching user/session security versions.
