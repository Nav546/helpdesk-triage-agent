---
title: Account locked out
category: account_lockout
keywords: locked out, account locked, lockout, too many attempts, cannot sign in, can't sign in, login failed
verify_identity: true
always_escalate: false
---
## Steps
1. Verify the caller's identity before unlocking.
2. Check the lockout source and time in the directory logs.
3. Unlock the account and ask the user to sign in.
4. Check for old saved passwords on other devices that may cause repeat lockouts.
## Escalate when
- The lockout repeats within the hour.
- The source of failed sign-ins is an unknown device.
