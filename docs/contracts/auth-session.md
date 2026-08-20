# Authentication and session contract

Public registration always creates a `client` and never accepts an authorization role. Passwords use Argon2id. Short-lived access JWTs remain in memory in the operations client. Opaque refresh tokens are stored only as hashes server-side and delivered through a secure HttpOnly cookie. Refresh rotation, reuse detection, revocation, and session/security-version checks are required.
