"use client";

import { notFound } from "next/navigation";
import { use, useMemo } from "react";
import { createPlatformApiClient } from "../../../lib/apiClient";
import { getProductDefinition } from "../../../products/registry";

type ProductPageProps = {
  params: Promise<{ productId: string }>;
};

export default function ProductPage({ params }: ProductPageProps) {
  const { productId } = use(params);
  const definition = getProductDefinition(productId);
  // Memoized so a re-render that isn't a real navigation doesn't hand the product a new client
  // instance and re-trigger its mount-time identity/runtime-config fetch.
  const client = useMemo(() => createPlatformApiClient(), []);

  if (!definition) {
    notFound();
  }

  const { Component } = definition;
  return <Component key={productId} client={client} />;
}
