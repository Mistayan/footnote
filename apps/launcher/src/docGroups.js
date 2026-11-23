const LANGS = { cargo: "Rust", pypi: "Python", npm: "JavaScript", go: "Go" };
export const UNUSED = "Not used by any project";

/** Doc sites by language, then the ones no project uses; one unnamed group when the build reports no usage. Inside a
 * group: still embedding first, then the most-used, then by name. */
export function groupDocs(docs) {
  const byOrder = (a, b) =>
    (a.state === "embedding" ? 0 : 1) - (b.state === "embedding" ? 0 : 1) ||
    (b.used_by?.length ?? 0) - (a.used_by?.length ?? 0) ||
    a.site.localeCompare(b.site);
  if (!docs.some((d) => Array.isArray(d.used_by))) return [{ name: null, docs: [...docs].sort(byOrder) }];
  const groups = new Map();
  for (const d of docs) {
    const name = d.used_by?.length ? (LANGS[d.ecosystem] ?? "Other") : UNUSED;
    groups.set(name, [...(groups.get(name) ?? []), d]);
  }
  return [...groups]
    .map(([name, list]) => ({ name, docs: list.sort(byOrder) }))
    .sort((a, b) => (a.name === UNUSED) - (b.name === UNUSED) || b.docs.length - a.docs.length);
}
