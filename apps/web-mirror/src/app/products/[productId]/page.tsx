"use client";

import { createInMemoryAsyncStorage, createWindowLocalStorageAdapter } from "@anytoolai/ce-kit";
import { notFound } from "next/navigation";
import { use, useMemo } from "react";
import { createPlatformApiClient } from "../../../lib/apiClient";
import { getRegisteredProduct } from "../../../products/registry";
import { createProductRunEventTracker } from "../../../products/runtime/productRunEventTracking";
import { createClientEventTracker } from "../../../products/runtime/clientEventTracker";

type ProductPageProps = {
  params: Promise<{ productId: string }>;
};

export default function ProductPage({ params }: ProductPageProps) {
  const { productId } = use(params);
  const product = getRegisteredProduct(productId);
  // Memoized so a re-render that isn't a real navigation doesn't hand the product a new client
  // instance and re-trigger its mount-time identity/runtime-config fetch.
  const client = useMemo(() => createPlatformApiClient(), []);
  const onEvent = useMemo(
    // Same fallback ProductRunPage itself uses for its own storage: `createWindowLocalStorageAdapter`
    // returns undefined outside the browser (SSR) or when localStorage is unavailable.
    () => createProductRunEventTracker(client, productId, createWindowLocalStorageAdapter() ?? createInMemoryAsyncStorage()),
    [client, productId],
  );
  const onEvent = useMemo(() => createClientEventTracker(client, productId), [client, productId]);

  if (!product) {
    notFound();
  }

  const { Component } = product;
  return <Component key={productId} client={client} onEvent={onEvent} />;
}
