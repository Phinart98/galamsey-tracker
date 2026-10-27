// Outside links come from the source register (docs/sources.json, field `link`), so every page links the same
// page for the same source. A missing id fails the build instead of shipping a dead link.
import fs from 'node:fs';
import path from 'node:path';

const register = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '../../docs/sources.json'), 'utf8')) as {
  sources: { id: string; link?: string }[];
};
const links = new Map(register.sources.filter((s) => s.link).map((s) => [s.id, s.link!]));

export function sourceLink(id: string): string {
  const link = links.get(id);
  if (!link) throw new Error(`docs/sources.json has no link for source "${id}"`);
  return link;
}
