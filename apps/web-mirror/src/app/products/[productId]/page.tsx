"use client";

import { notFound } from "next/navigation";
import { use, useMemo } from "react";
import { createPlatformApiClient } from "../../../lib/apiClient";
import { getRegisteredProduct } from "../../../products/registry";
import { getClientStorage } from "../../../products/runtime/clientStorage";
import { createProductRunEventTracker } from "../../../products/runtime/productRunEventTracking";

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
    // The same per-client storage ProductRunPage uses for the guest id -- code review finding: a
    // fresh in-memory fallback per `productId` change rotated `web_session_id` when navigating
    // between products with no usable localStorage, but it should only rotate after 30 minutes
    // of inactivity.
    () => createProductRunEventTracker(client, productId, getClientStorage(client)),
    [client, productId],
  );
  // A fresh id every time `productId` actually changes -- including a return to a productId
  // already visited this tab session (`client` above is memoized across that navigation, per its
  // own comment) -- scopes ProductRunPage's once-per-visit product_viewed/form_started dedupe to
  // one real landing on this product instead of the client's whole lifetime (code review finding).
  // `productId` is a dependency purely to force recomputation on that change; the callback itself
  // has no use for its value.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const visitId = useMemo(() => crypto.randomUUID(), [productId]);

  if (!product) {
    notFound();
  }

  const { Component } = product;
  return <Component key={productId} client={client} onEvent={onEvent} visitId={visitId} />;
}
