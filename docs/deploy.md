# Deploying Voicedex (Google Cloud Run)

Production runs on Cloud Run (`us-central1`, scale-to-zero, max 2 instances) behind Cloudflare.
Every push to `main` runs CI; when it passes, the `deploy` job builds the Docker image, pushes it to
Artifact Registry and deploys it. GitHub authenticates to Google with Workload Identity Federation —
there are no service-account keys anywhere.

## One-time setup

```bash
PROJECT=voicedex-prod            # GCP project id (billing linked, ₹100 budget alert)
REPO=chandradot99/voicedex       # GitHub owner/repo (update after renaming the repo)
REGION=us-central1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com sts.googleapis.com

# Image registry; keep only the newest images (stays within the free 0.5 GB)
gcloud artifacts repositories create voicedex --repository-format=docker --location=$REGION
cat > cleanup.json <<'JSON'
[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":3}},
 {"name":"delete-older","action":{"type":"Delete"},"condition":{"tagState":"any","olderThan":"1d"}}]
JSON
gcloud artifacts repositories set-cleanup-policies voicedex --location=$REGION --policy=cleanup.json --no-dry-run

# Deployer identity, usable only by GitHub Actions runs of this repo
gcloud iam service-accounts create github-deployer
SA=github-deployer@$PROJECT.iam.gserviceaccount.com
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$SA --role=$role --condition=None
done
gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository \
  --attribute-condition="assertion.repository=='$REPO'"
POOL=$(gcloud iam workload-identity-pools describe github --location=global --format='value(name)')
gcloud iam service-accounts add-iam-policy-binding $SA --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO"

# Tell the workflow where to deploy
gh variable set GCP_PROJECT_ID --body $PROJECT
gh variable set GCP_WIF_PROVIDER --body "$POOL/providers/github"
gh variable set GCP_DEPLOY_SA --body $SA
```

## Domain (Cloudflare)

1. `gcloud beta run domain-mappings create --service voicedex --domain voicedex.dev --region $REGION`
   and add the DNS records it prints in Cloudflare as **DNS only** (grey cloud) until Google has
   issued the certificate (`gcloud beta run domain-mappings describe ...` shows it ready), then switch
   them to Proxied.
2. Cloudflare → SSL/TLS → **Full (strict)**.
3. Cloudflare → Caching → Cache Rules: hostname `voicedex.dev` → *Eligible for cache*, edge TTL
   *use origin Cache-Control* (the app sends `public, max-age=300`). This serves most visits while
   Cloud Run is scaled to zero.
4. `gh variable set TRUST_CF_CONNECTING_IP --body true` and redeploy (rate-limit key = visitor IP).

## Cost guardrails

Free tier covers this app's traffic. Keep a budget alert ($1) on the billing account; `--max-instances 2`
caps spend from traffic spikes.
