import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import tokens from "../src/tokens.json";

type Rgb = [number, number, number];

function rgb(value: string): Rgb {
  if (value.startsWith("#")) {
    return [1, 3, 5].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16)) as Rgb;
  }
  return value.match(/[\d.]+/g)!.slice(0, 3).map(Number) as Rgb;
}

function mix(foreground: Rgb, background: Rgb, alpha: number): Rgb {
  return foreground.map((channel, index) => channel * alpha + background[index]! * (1 - alpha)) as Rgb;
}

function composite(value: string, background: Rgb): Rgb {
  return mix(rgb(value), background, value.startsWith("rgba") ? Number(value.match(/[\d.]+/g)![3]) : 1);
}

function luminance(color: Rgb): number {
  const linear = color.map((channel) => {
    const srgb = channel / 255;
    return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
  });
  return linear[0]! * 0.2126 + linear[1]! * 0.7152 + linear[2]! * 0.0722;
}

function contrast(text: Rgb, background: Rgb): number {
  const a = luminance(text);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

// Follow the component's actual semantic pair, so reverting Button to --color-text also fails.
const buttonCss = readFileSync("src/Button.module.css", "utf-8");
const primary = buttonCss.match(/\.primary\s*{([^}]*)}/s)![1]!;
const colors = new Map(Object.entries(tokens.colors).map(([key, value]) => [
  key.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase(), value,
]));

it("keeps primary text at 4.5:1 across the complete accent gradient", () => {
  const colorName = primary.match(/color:\s*var\(--color-([\w-]+)\)/)![1]!;
  const gradientName = primary.match(/background:\s*var\(--gradient-(\w+)\)/)![1]!;
  const gradient = tokens.gradients[gradientName as keyof typeof tokens.gradients];
  const stops = [...gradient.matchAll(/#[\da-f]{6}/gi)].map((match) => rgb(match[0]));
  expect(stops).toHaveLength(2);
  const text = rgb(colors.get(colorName)!);
  const samples = Array.from({ length: 1001 }, (_, i) => mix(stops[1]!, stops[0]!, i / 1000));
  expect(Math.min(...samples.map((background) => contrast(text, background)))).toBeGreaterThanOrEqual(4.5);
  // The historical light-text pair must be rejected by the same calculation.
  expect(Math.min(...samples.map((background) => contrast(rgb(tokens.colors.text), background)))).toBeLessThan(4.5);
});

it("keeps secondary text readable on the supported page, card, nested field and hover surfaces", () => {
  for (const base of [tokens.colors.background, tokens.colors.backgroundSecondary, tokens.colors.backgroundTertiary]) {
    const page = rgb(base);
    const card = composite(tokens.colors.surfaceCard, page);
    const field = composite(tokens.colors.surfaceCard, card);
    const hover = composite(tokens.colors.surfaceHover, card);
    for (const background of [page, card, field, hover]) {
      expect(contrast(composite(tokens.colors.textSecondary, background), background)).toBeGreaterThanOrEqual(4.5);
    }
  }
});
