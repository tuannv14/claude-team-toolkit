---
name: aws-s3
description: List, upload, download, sync, and manage AWS S3 buckets via the AWS CLI with multi-account profile support. Use when the user asks to list S3 buckets, upload/download files, sync directories, generate presigned URLs, or check bucket contents. Profiles map to AWS CLI named profiles (~/.aws/credentials) plus this skill's own metadata. Switch with --profile <name> or AWS_S3_PROFILE env var.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /aws-s3 — S3 operations (multi-account)

Wraps `aws s3` and `aws s3api` CLI for safer, audited operations. Profiles
mirror AWS CLI's named profile system (`~/.aws/credentials`) so this skill
shares config with any other AWS tool the user has.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `AWS_S3_PROFILE` env → `[default]`.

## Dependencies

AWS CLI v2: `aws --version`. Install:

```bash
# Windows
choco install awscli         # or msi from aws.amazon.com/cli
# macOS
brew install awscli
# Linux
sudo apt install awscli      # or follow AWS docs for v2
```

## Profile config

This skill uses **AWS CLI's native config**, not a separate INI file —
because that's where `aws-vault`, Terraform, and every other AWS tool already
look. Two files (both mode 600):

`~/.aws/credentials`:
```ini
[default]
aws_access_key_id = AKIAxxxxxxxxxxxxxxxx
aws_secret_access_key = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

[work]
aws_access_key_id = AKIAxxxxxxxxxxxxxxxx
aws_secret_access_key = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`~/.aws/config`:
```ini
[default]
region = us-east-1
output = json

[profile work]
region = ap-southeast-1
output = json
# require MFA / role assumption — recommended for prod
mfa_serial = arn:aws:iam::123456789012:mfa/username
role_arn = arn:aws:iam::123456789012:role/EngineerRole
source_profile = default
```

**Configure interactively:**
```bash
aws configure --profile <name>
```

**Better: use IAM Identity Center (SSO):**
```bash
aws configure sso --profile <name>
aws sso login --profile <name>     # refresh tokens
```

SSO avoids long-lived access keys → strongly recommended for orgs.

## Helpers

```bash
PROF="${PROFILE:-${AWS_S3_PROFILE:-default}}"

# Validate profile name (letters, digits, hyphen, underscore only)
case "$PROF" in
  ''|*[!a-zA-Z0-9_-]*) echo "Invalid profile name: $PROF" >&2; return 1 ;;
esac

# Verify creds work before any op
aws --profile "$PROF" sts get-caller-identity >/dev/null || {
  echo "Auth failed for profile $PROF. Run: aws configure --profile $PROF (or aws sso login --profile $PROF)" >&2
  return 1
}
```

## Dispatch

### `buckets` — list buckets

```bash
aws --profile "$PROF" s3 ls
```

### `ls <s3://bucket/prefix>` — list objects

```bash
aws --profile "$PROF" s3 ls "$S3_PATH" --human-readable --summarize
```

### `cp <src> <dst>` — copy (one direction)

`<src>` and `<dst>` can be local path or `s3://...`.

```bash
aws --profile "$PROF" s3 cp "$SRC" "$DST"
```

### `sync <src> <dst> [--delete] [--exclude pattern]`

`--delete` removes files in dst not in src — DANGEROUS, requires confirm.

```bash
source "$HOME/.claude-team-toolkit/lib/confirm.sh"

# Build args as array — never use unquoted variable splitting for flags
EXTRA=()
if [ "$DELETE" = "true" ]; then
  ctt_warn_destructive "Sync with --delete: files in $DST not in $SRC will be REMOVED"
  ctt_confirm "Proceed with $SRC → $DST (--delete) on profile $PROF?" "SYNC" || return 1
  EXTRA+=(--delete)
fi
[ -n "$EXCLUDE" ] && EXTRA+=(--exclude "$EXCLUDE")

aws --profile "$PROF" s3 sync "$SRC" "$DST" "${EXTRA[@]}"
ctt_audit_log aws-s3 "sync $SRC → $DST ${EXTRA[*]}"
```

### `presign <s3://bucket/key> [--expires-in N]` — generate presigned URL

```bash
aws --profile "$PROF" s3 presign "$S3_PATH" --expires-in "${EXPIRES:-3600}"
```

Default 1h. Cap at 7d (604800s) — that's the AWS max. Anything longer fails.

### `info <s3://bucket/key>` — object metadata

```bash
case "$1" in
  s3://*/*) ;;
  *) echo "Need s3://bucket/key path" >&2; return 1 ;;
esac
BUCKET="${1#s3://}"; BUCKET="${BUCKET%%/*}"
KEY="${1#s3://*/}"
[ -z "$KEY" ] && { echo "Empty key" >&2; return 1; }
aws --profile "$PROF" s3api head-object --bucket "$BUCKET" --key "$KEY"
```

### `bucket-info <bucket>` — bucket-level config

```bash
echo "=== Versioning ==="; aws --profile "$PROF" s3api get-bucket-versioning --bucket "$1"
echo "=== Encryption ==="; aws --profile "$PROF" s3api get-bucket-encryption --bucket "$1" 2>/dev/null || echo "Not configured"
echo "=== Public access block ==="; aws --profile "$PROF" s3api get-public-access-block --bucket "$1" 2>/dev/null
echo "=== Lifecycle ==="; aws --profile "$PROF" s3api get-bucket-lifecycle-configuration --bucket "$1" 2>/dev/null || echo "None"
```

### `rm <s3://path> [--recursive]` — DESTRUCTIVE

```bash
ctt_warn_destructive "Delete $S3_PATH ${RECURSIVE:+(recursive)} on profile $PROF"
ctt_confirm "Type DELETE to confirm:" "DELETE" || return 1
aws --profile "$PROF" s3 rm "$S3_PATH" ${RECURSIVE:+--recursive}
ctt_audit_log aws-s3 "rm $S3_PATH ${RECURSIVE:+recursive}"
```

## Safety

- **Never write AWS keys into this skill's audit log.** The skill only
  records bucket/key paths and operations, not credentials.
- **Respect `--dryrun`**: every mutating command supports `--dryrun`. Use it
  by default when generating commands; ask user before removing it.
- **Cross-account caution**: ALWAYS verify `aws sts get-caller-identity`
  matches the expected account before destructive ops on shared buckets.
- **Public buckets**: if `bucket-info` shows `BlockPublicAcls=false`, warn
  the user — that's likely a misconfiguration.
- **Server-Side Encryption**: prefer KMS (`--sse aws:kms`) over AES-256 for
  buckets containing PII / customer data.
- **Presigned URLs are credentials** — they grant access to anyone with the
  link. Don't paste in public chat. Use shortest expiry that works.
- **Bucket public ACL**: blocked by default in new AWS accounts since 2023.
  If user wants to make object public, use bucket policy + presigned URLs
  instead of `--acl public-read` (which usually fails anyway).

## Token-saving tip

Use **IAM Identity Center (SSO)** instead of long-lived access keys. Tokens
auto-rotate, are scoped to a specific role/account, and are audited.
