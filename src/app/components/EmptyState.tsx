export function EmptyState() {
  return (
    <section className="empty">
      <h2>Ready for the revealed task</h2>
      <p>
        Load the demo now, then upload the organizers&rsquo; file once the prompt arrives. The parser detects columns,
        delimiters and types on its own — there is no fixed schema to rewrite.
      </p>
      <code>CSV · TSV · semicolon or pipe delimited · JSON array of objects</code>
    </section>
  );
}
