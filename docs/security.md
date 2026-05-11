# Security

## Protections built into DOCTA

- **Path traversal protection** via `utils/security.py` — all input and output paths are validated before use
- **Symlink validation** — symlinked files are blocked by default; opt in with `--allow-symlinks`
- **Output path validation** — prevents writing outside the project directory
- **Hash-based integrity checking** — SHA-256 is used for all file comparisons
- **No secrets in repository** — API keys and credentials are read from environment variables only
- **OAuth 2.0 authentication** for all GraphQL API access

## Best practices

- Never commit credentials — use environment files (`.env`) and add them to `.gitignore`
- Set restrictive file permissions on credential files: `chmod 600 .env`
- Use the `.env.example` file as a reference for required variable names
- Rotate API keys and OAuth secrets on a regular schedule

## Reporting a vulnerability

See [SECURITY.md](https://github.com/arin-deloatch/docta/blob/main/SECURITY.md) for the responsible disclosure policy and reporting instructions.
