FROM node:22-slim AS build
WORKDIR /app
RUN corepack enable
COPY . .
RUN pnpm install --frozen-lockfile
ARG PLATFORM_API_BASE_URL=http://platform-api:8000
ARG NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
ENV PLATFORM_API_BASE_URL=$PLATFORM_API_BASE_URL
ENV NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS=$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
RUN test -n "$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS"
RUN pnpm --filter @anytoolai/web-mirror build

FROM node:22-slim AS runtime
WORKDIR /app
RUN corepack enable
ENV NODE_ENV=production
COPY --from=build /app /app
EXPOSE 3000
CMD ["pnpm", "--filter", "@anytoolai/web-mirror", "exec", "next", "start", "-p", "3000"]
