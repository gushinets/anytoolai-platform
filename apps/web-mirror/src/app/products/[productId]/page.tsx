"use client";

import { notFound } from "next/navigation";
import { use, useMemo } from "react";
import { createPlatformApiClient } from "../../../lib/apiClient";
import { getRegisteredProduct } from "../../../products/registry";
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
  const onEvent = useMemo(() => createClientEventTracker(client, productId), [client, productId]);

  if (!product) {
    notFound();
  }

  const { Component } = product;
  return <Component key={productId} client={client} onEvent={onEvent} />;
}
