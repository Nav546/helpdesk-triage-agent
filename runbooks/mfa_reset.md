---
title: MFA reset or new phone
category: mfa_reset
keywords: mfa, authenticator, new phone, lost phone, one time code, otp, verification code, multi factor
verify_identity: true
always_escalate: false
---
## Steps
1. Verify the caller's identity with a one-time passcode sent to a registered contact and a challenge question.
2. Only after both checks pass, register a new authentication method for the user.
3. Ask the user to confirm they can approve a sign-in on the new device.
4. Record the verification result in the ticket.
## Escalate when
- Either verification check fails.
- The user cannot be reached on a registered contact.
