FROM node:24-slim AS build
WORKDIR /app
RUN corepack enable
COPY . .
RUN pnpm install --frozen-lockfile
ARG PLATFORM_API_BASE_URL=http://platform-api:8000
ARG NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
ARG ANYTOOLAI_WEB_BASE_PATH
ENV PLATFORM_API_BASE_URL=$PLATFORM_API_BASE_URL
ENV NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS=$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
ENV ANYTOOLAI_WEB_BASE_PATH=$ANYTOOLAI_WEB_BASE_PATH
RUN test -n "$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS"
RUN pnpm --filter @anytoolai/web-mirror build

FROM node:24-slim AS runtime
WORKDIR /app/apps/web-mirror
ARG ANYTOOLAI_WEB_BASE_PATH
ENV NODE_ENV=production
ENV ANYTOOLAI_WEB_BASE_PATH=$ANYTOOLAI_WEB_BASE_PATH
COPY --from=build /app /app
RUN chown -R node:node .next
USER node
EXPOSE 3000
# Next answers and its same-origin /v1/* rewrite reaches platform-api for the first enabled
# product. Unhealthy while the API is down or ANYTOOLAI_ENABLED_PRODUCT_IDS is unset.
HEALTHCHECK --interval=5s --timeout=5s --start-period=20s --retries=12 \
    CMD ["node", "-e", "const id=(process.env.ANYTOOLAI_ENABLED_PRODUCT_IDS||'').split(',')[0].trim(); \
if(!id) process.exit(1); \
fetch('http://127.0.0.1:3000/v1/products/'+encodeURIComponent(id)+'/runtime-config') \
.then(async r=>{if(!r.ok||(await r.json()).product_id!==id) process.exit(1)}) \
.catch(()=>process.exit(1))"]
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
