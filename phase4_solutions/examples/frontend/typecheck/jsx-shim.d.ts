// Minimal JSX types so the examples type-check on their own (`npx tsc -p examples/frontend`).
// Inside your real React app, React's own types replace this file; do not copy it there.
declare namespace JSX {
  interface Element {}
  interface IntrinsicAttributes {
    key?: string | number;
  }
  interface IntrinsicElements {
    [tag: string]: Record<string, unknown>;
  }
}
