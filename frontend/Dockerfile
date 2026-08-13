# syntax=docker/dockerfile:1

# --- Stage 1: install dependencies -----------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
# Install only what's needed to resolve the lockfile, cached on package files.
COPY package.json package-lock.json* ./
RUN npm ci

# --- Stage 2: build the app -------------------------------------------------
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `next/font/google` downloads + self-hosts fonts at build time (needs network
# during build). Produces .next/standalone via output: "standalone".
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Stage 3: minimal production runtime ------------------------------------
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run as an unprivileged user.
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

# Copy the standalone server, static assets, and public files.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# server.js is emitted by Next's standalone output.
CMD ["node", "server.js"]
