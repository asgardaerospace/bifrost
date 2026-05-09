# syntax=docker/dockerfile:1.6
#
# Bifrost frontend — Next.js production multi-stage build using the
# `output: "standalone"` Next.js mode for a minimal runtime image.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund


FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 bifrost \
 && adduser  --system --uid 1001 --ingroup bifrost bifrost

COPY --from=builder /app/public ./public
COPY --from=builder --chown=bifrost:bifrost /app/.next/standalone ./
COPY --from=builder --chown=bifrost:bifrost /app/.next/static ./.next/static

USER bifrost
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
