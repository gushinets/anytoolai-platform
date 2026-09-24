import Link from "next/link";
import { listRegisteredProducts } from "../products/registry";

export default function HomePage() {
  const products = listRegisteredProducts().filter((product) => product.enabled);
  return (
    <main className="page-container">
      <h1>AnytoolAI</h1>
      <ul>
        {products.map((product) => (
          <li key={product.productId}>
            <Link href={`/products/${product.productId}`}>{product.messages.en.title}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
