---
title: Password reset
category: password_reset
keywords: password, forgot password, reset password, expired, password expired, change password
verify_identity: true
always_escalate: false
---
## Steps
1. Verify the caller's identity using the approved verification questions before any change.
2. Direct the user to the self-service reset portal if they are registered.
3. If not registered, an analyst resets the password with a temporary value and forces a change at next sign-in.
4. Confirm the user can sign in and update saved passwords on their phone and laptop.
## Escalate when
- Identity cannot be verified.
- The account shows sign-ins from unexpected locations.
