import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page-container">
      <h1>Page not found</h1>
      <p>
        <Link href="/">Back to all products</Link>
      </p>
    </main>
  );
}
