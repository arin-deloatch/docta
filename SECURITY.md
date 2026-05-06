# Security Policy

## Supported versions

Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
|---------|-----------|
| latest  | yes       |
| older   | no        |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's private security advisory instead:

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Describe the issue, affected versions, and steps to reproduce.

You will receive an acknowledgment within **7 days** and a patch or mitigation plan
within **30 days** where feasible.

## Secrets and credentials

- API keys and credentials must be supplied via environment variables only.
- Use `.env.example` as a reference for what variables are expected — it contains no
  real values.
- Never commit secrets, tokens, or credentials to the repository.
- Do not log raw credentials or API keys at any log level.
