# Vercel Deployment Setup Guide

## Step 1: Login to Vercel CLI

```bash
vercel login
```

Follow the prompts to authenticate.

---

## Step 2: Link Your Project

If this is a new project:
```bash
vercel link
```

Or if you already have a Vercel project, make sure you're in the correct directory.

---

## Step 3: Set Environment Variables

### Option A: Set All Variables at Once (Recommended)

Run these commands one by one:

```bash
# 1. Database URL (Neon PostgreSQL)
echo "postgresql://user:password@host-pooler.region.aws.neon.tech/dbname?sslmode=require" | vercel env add DATABASE_URL production

# 2. OpenAI API Key
echo "YOUR_OPENAI_API_KEY_HERE" | vercel env add OPENAI_API_KEY production

# 3. OpenAI Assistant ID
echo "YOUR_ASSISTANT_ID_HERE" | vercel env add OPENAI_ASSISTANT_ID production

# 4. OpenAI Vector Store ID
echo "YOUR_VECTOR_STORE_ID_HERE" | vercel env add OPENAI_VECTOR_STORE_ID production

# 5. Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
echo "YOUR_SECRET_KEY_HERE" | vercel env add SECRET_KEY production

# 6. Vercel flag
echo "true" | vercel env add VERCEL production
```

### Option B: Interactive Mode

For each variable, run:
```bash
vercel env add <VARIABLE_NAME> production
```

Then paste the value when prompted.

---

## Step 4: Verify Environment Variables

Check that all variables were set correctly:

```bash
vercel env ls
```

You should see:
- DATABASE_URL
- OPENAI_API_KEY
- OPENAI_ASSISTANT_ID
- OPENAI_VECTOR_STORE_ID
- SECRET_KEY
- VERCEL

---

## Step 5: Deploy to Production

```bash
vercel --prod
```

This will:
1. Build your application
2. Deploy to production
3. Use the environment variables you just set

---

## Step 6: Verify Deployment

After deployment completes:

1. Visit your production URL (shown in terminal)
2. Test user registration/login
3. Test chat functionality
4. Check Vercel logs: `vercel logs --prod`
5. Verify database persistence

---

## Important Notes

### Environment Variable Scopes

Vercel has three environment scopes:
- **Production**: Used in `vercel --prod` deployments
- **Preview**: Used in preview deployments (git branches)
- **Development**: Used in local development with `vercel dev`

We set everything for **production** only. To also set for preview/development:

```bash
# Add to all environments
echo "value" | vercel env add VARIABLE_NAME production preview development
```

### Security Best Practices

1. ✅ **Never commit .env file** (already in .gitignore)
2. ✅ **Use strong SECRET_KEY** (generated: cb5be0d2...)
3. ⚠️ **Rotate secrets periodically** (every 90 days)
4. ⚠️ **Monitor Vercel audit logs** (check who accesses env vars)
5. ⚠️ **Enable IP allowlist on Neon** (optional extra security)

### Generated SECRET_KEY

Your new strong SECRET_KEY:
```
cb5be0d2e6afb16d791e8e48b76747413a16b325cfbea91e1c626b82a95cf05f
```

**⚠️ Important:** This replaces the weak default key in your code. Your old sessions will be invalidated (users will need to login again).

---

## Troubleshooting

### Error: "No existing credentials found"
```bash
vercel login
```

### Error: "Project not found"
```bash
vercel link
```
Then select or create your project.

### Error: "Environment variable already exists"
Remove it first:
```bash
vercel env rm VARIABLE_NAME production
```
Then add again.

### View all environment variables
```bash
vercel env ls
```

### Pull environment variables to local .env
```bash
vercel env pull
```
This creates a `.env.local` file with your Vercel environment variables.

### Remove an environment variable
```bash
vercel env rm VARIABLE_NAME production
```

---

## Post-Deployment Checklist

After deploying, verify:

- [ ] Application loads without errors
- [ ] User registration works
- [ ] User login works
- [ ] Sessions persist across page refreshes
- [ ] Database queries work (check user profile, packs, etc.)
- [ ] OpenAI chat responses work
- [ ] No errors in Vercel logs: `vercel logs --prod`

---

## Quick Reference: All Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| DATABASE_URL | postgresql://neondb_owner:npg_... | Neon PostgreSQL connection |
| OPENAI_API_KEY | sk-proj-bzB7... | OpenAI API authentication |
| OPENAI_ASSISTANT_ID | asst_kxFV... | OpenAI Assistant for RAG |
| OPENAI_VECTOR_STORE_ID | vs_692e... | Vector store for documents |
| SECRET_KEY | cb5be0d2... | Flask session encryption |
| VERCEL | true | Flag for Vercel environment |

---

## Next Steps After Deployment

1. **Test with 10 users** (current goal)
2. **Migrate file storage to Vercel Blob** (critical next step)
3. **Add error monitoring** (Sentry)
4. **Add rate limiting** (Flask-Limiter)
5. **Security hardening** (CORS, CSRF)

---

## Support

- Vercel CLI Docs: https://vercel.com/docs/cli
- Environment Variables: https://vercel.com/docs/concepts/projects/environment-variables
- Troubleshooting: https://vercel.com/docs/cli/troubleshooting

---

**Ready to deploy?**

```bash
# 1. Login
vercel login

# 2. Link project
vercel link

# 3. Set environment variables (use commands above)

# 4. Deploy
vercel --prod
```

Good luck! 🚀
