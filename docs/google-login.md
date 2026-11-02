# Google login

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `backend/.env` using a Google OAuth web application client. Keep the secret on the backend. `FRONTEND_URL` defaults to `http://localhost:5173`.

Register this exact authorized redirect URI in Google Cloud:

```
http://localhost:5173/auth/callback/google
```

Restart the backend after configuration changes. Open the app at `http://localhost:5173` (use the same origin throughout login). If the OAuth app is in testing, add the signing-in account as a test user.

The authorization code flow uses PKCE and a ten-minute, single-use state tied to the initiating browser tab. The backend retrieves a verified Google email and identifies returning users by Google's stable subject. Existing password accounts are not automatically linked by email; use the original login method for those accounts. New Google users complete onboarding.

Reference: https://developers.google.com/identity/openid-connect/openid-connect
