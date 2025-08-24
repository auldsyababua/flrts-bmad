# Environment Setup Guide

## Overview

This document outlines the process for provisioning separate Supabase and Cloudflare instances for the preview/development environment. The production environment uses the `main` branch, while the preview environment uses the `develop` branch.

## Environment Architecture

### Production Environment
- **Branch**: `main`
- **URL**: Production Render URL
- **Database**: Production Supabase instance
- **Services**: Production Cloudflare services

### Preview/Development Environment
- **Branch**: `develop`
- **URL**: Preview Render URL
- **Database**: Separate Supabase instance
- **Services**: Separate Cloudflare services

## Setup Process

### 1. Supabase Setup

#### Create New Supabase Project
1. Log into [Supabase Dashboard](https://app.supabase.com)
2. Click "New Project"
3. Configure project:
   - **Name**: `flrts-dev` (or similar)
   - **Database Password**: Generate secure password
   - **Region**: Same as production for consistency
4. Wait for project provisioning

#### Configure Database Schema
1. Navigate to SQL Editor in Supabase Dashboard
2. Run the schema creation scripts from `src/database/schema.sql`
3. Configure Row Level Security policies as needed
4. Enable required extensions (vector, etc.)

#### Obtain Connection Details
1. Go to Settings → API
2. Copy the following for `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_KEY`

### 2. Cloudflare Setup

#### Cloudflare Vectorize
1. Log into [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to Workers & Pages → Vectorize
3. Create new index:
   - **Name**: `flrts-dev-vectors`
   - **Dimensions**: Match production settings
   - **Metric**: cosine
4. Note the index name for configuration

#### Cloudflare KV/Redis
1. In Cloudflare Dashboard, navigate to Workers & Pages → KV
2. Create new namespace:
   - **Name**: `flrts-dev-cache`
3. Note the namespace ID

#### Cloudflare API Configuration
1. Navigate to My Profile → API Tokens
2. Create new token with permissions:
   - Account: Vectorize:Edit
   - Account: Workers KV Storage:Edit
3. Save token securely

### 3. Render.com Configuration

#### Create Preview Service
1. Log into [Render Dashboard](https://dashboard.render.com)
2. Select your FLRTS service
3. Go to Settings → Build & Deploy
4. Add Preview Environment:
   - **Branch**: `develop`
   - **Auto-Deploy**: Yes

#### Environment Variables
Set the following environment variables for the preview instance:

```bash
# Supabase (Development)
SUPABASE_URL=your-dev-supabase-url
SUPABASE_ANON_KEY=your-dev-anon-key
SUPABASE_SERVICE_KEY=your-dev-service-key

# Cloudflare (Development)
CLOUDFLARE_ACCOUNT_ID=your-account-id
CLOUDFLARE_API_TOKEN=your-dev-api-token
CLOUDFLARE_VECTORIZE_INDEX=flrts-dev-vectors
CLOUDFLARE_KV_NAMESPACE_ID=your-dev-kv-namespace-id

# OpenAI (can be same as production)
OPENAI_API_KEY=your-openai-key

# Telegram (Development Bot)
TELEGRAM_BOT_TOKEN=your-dev-bot-token
TELEGRAM_WEBHOOK_URL=https://your-preview-url.onrender.com/webhook

# Other
ENVIRONMENT=development
LOG_LEVEL=debug
```

### 4. GitHub Actions Configuration

The GitHub Actions workflow will be configured to deploy the `develop` branch automatically to the preview environment. See `.github/workflows/preview-deploy.yml` for the implementation.

## Environment Management

### Switching Between Environments

#### Local Development
Use `.env.development` and `.env.production` files:

```bash
# Development
cp .env.development .env

# Production
cp .env.production .env
```

#### Database Migrations
1. Always test migrations on development first
2. Use Supabase migrations feature for version control
3. Apply to production only after validation

### Monitoring

#### Health Checks
- Production: `https://production-url/health`
- Development: `https://preview-url/health`

#### Logs
- Render Dashboard shows logs for each environment
- Supabase provides database logs
- Cloudflare provides service-specific logs

## Best Practices

1. **Never share credentials** between environments
2. **Test thoroughly** in development before merging to main
3. **Keep schemas in sync** between environments
4. **Regular backups** of both databases
5. **Monitor costs** for duplicate services

## Troubleshooting

### Common Issues

#### Database Connection Errors
- Verify Supabase project is active
- Check firewall/network settings
- Confirm environment variables are correct

#### Cloudflare API Errors
- Verify API token permissions
- Check rate limits
- Ensure index/namespace exists

#### Deployment Failures
- Check Render build logs
- Verify environment variables
- Ensure branch is pushed to GitHub

## Cost Considerations

Running duplicate environments will approximately double infrastructure costs:
- Supabase: Free tier may be sufficient for development
- Cloudflare: Most services have generous free tiers
- Render: Preview environments may incur additional costs

## Security Notes

1. Use different API keys for each environment
2. Restrict development database access
3. Use separate Telegram bots for each environment
4. Implement IP whitelisting where possible
5. Rotate credentials regularly