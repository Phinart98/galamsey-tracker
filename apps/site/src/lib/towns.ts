// Finding a town by name. Shared by the home page search and the map's town filter, which both run in the browser
// on /towns.json (pages/towns.json.ts), so this file must not use anything from Node.

// [name, district, hectares within 1 km, patches, patch ids largest first, lat, lon]
export type TownRow = [string, string | null, number, number, string[], number, number];

// Letters and digits only, with no accents or capitals: "Dunkwa-on-Offin" and "dunkwa on offin" are the same
export const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');

// Spellings people use for the same name (OpenStreetMap has some of each), made the same on both sides of a search
const SPELLINGS: [string, string][] = [
  ['kyebi', 'kibi'], ['akyem', 'akim'], ['kwawu', 'kwahu'], ['akuapem', 'akwapim'], ['wasa', 'wassa'], ['obuase', 'obuasi'],
];
const respell = (s: string) => SPELLINGS.reduce((t, [from, to]) => (t.includes(to) ? t : t.replaceAll(from, to)), s);
const key = (s: string) => respell(fold(s));

// How well a town's name matches what was typed: 0 the same, 1 starts with it, 2 contains it, 3 no match
export function matchRank(name: string, typed: string) {
  const n = key(name);
  const t = key(typed);
  return n === t ? 0 : n.startsWith(t) ? 1 : n.includes(t) ? 2 : 3;
}

// What a town is called in links and the map's town filter: "Name (District)", the same from week to week.
// OpenStreetMap has a few names more than once in one district. Two are told apart by where each lies from the
// other ("Brofoyedru, north (Adansi North)"); three or more, or two on the same spot, are numbered from north to south.
export function townKeys(rows: TownRow[]): string[] {
  const plain = rows.map(([name, district]) => (district ? `${name} (${district})` : name));
  const groups = new Map<string, number[]>();
  plain.forEach((k, i) => groups.set(k, [...(groups.get(k) ?? []), i]));
  const keys = [...plain];
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    let labels: string[] | null = null;
    if (group.length === 2) {
      const [a, b] = group.map((i) => rows[i]);
      const dLat = a[5] - b[5];
      const dLon = a[6] - b[6];
      if (dLat || dLon) {
        labels = Math.abs(dLat) >= Math.abs(dLon)
          ? (dLat > 0 ? ['north', 'south'] : ['south', 'north'])
          : (dLon > 0 ? ['east', 'west'] : ['west', 'east']);
      }
    }
    const order = [...group].sort((i, j) => rows[j][5] - rows[i][5] || rows[i][6] - rows[j][6] || i - j);
    group.forEach((i, n) => {
      const label = labels ? labels[n] : `no. ${order.indexOf(i) + 1}`;
      const [name, district] = rows[i];
      keys[i] = district ? `${name}, ${label} (${district})` : `${name}, ${label}`;
    });
  }
  return keys;
}

// The town meant by a link or a typed name: the exact key, else a town with exactly that name (spellings and
// capitals aside), in the named district if one was given, the one with most cleared land if several. A partial
// name finds nothing here: the list under the box is for those.
export function findTown(rows: TownRow[], keys: string[], typed: string): number {
  const exact = keys.indexOf(typed);
  if (exact >= 0) return exact;
  const [, name, district] = typed.match(/^(.*?)(?:\s*\(([^)]*)\))?\s*$/) ?? [];
  // In the named district first, then most cleared land
  const score = ([, d, ha]: TownRow) => (district && fold(d ?? '') === fold(district) ? 1e9 : 0) + ha;
  let best = -1;
  rows.forEach((row, i) => {
    if (matchRank(row[0], name ?? typed) === 0 && (best < 0 || score(row) > score(rows[best]))) best = i;
  });
  return best;
}
