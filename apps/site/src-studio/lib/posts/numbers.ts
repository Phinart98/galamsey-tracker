// Posts built around a number: football pitches a day, the licence split, a district in the spotlight, districts
// compared, patch sizes, the map of every patch, the water test, and the month in review
import { active, coverage, summary } from '../../../src/lib/data';
import { LICENCE_SHORT, PITCH_HA, count, hectares, nearText, num, pct, placeName, shortDate, tidyDistrict } from '../../../src/lib/format';
import { barsPost, districtPost, licencePost, mapPost, ratePost, statPost } from '../designs';
import { SITE, dataDate, districtTotals, likelyLand, near, newest, photo, pick, pitches, reviewMonth, unlicensed, type Post } from './rules';
import waterMap from '../../../src/data/water-map.json';

export const numberPosts: Post[] = [];
const AREAS = `the ${count(coverage.length)} areas of the southern gold belt we cover`;
const unlicensedHa = unlicensed.reduce((t, p) => t + p.ha, 0);

// Football pitches a day: an average of our own 12-month total, not a claim that it is rising
if (summary && unlicensedHa > 0) {
  const perDay = Math.round(unlicensedHa / PITCH_HA / 365);
  numberPosts.push({
    slug: 'rate',
    kind: 'Football pitches a day',
    title: 'Football pitches a day',
    alt: `${perDay} football pitches drawn in rows: on average, the land cleared with no licence to mine every day in ${AREAS}. ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}.`,
    text: `Every day, on average, about ${perDay} football pitches of land are cleared with no licence to mine in the parts of Ghana's southern gold belt we track.

That is ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}, seen by satellite.`,
    reply: `Where it is, with before and after pictures of every patch: ${SITE}/`,
    render: () => ratePost({
      top: 'Every day, in the gold belt areas we track',
      perDay,
      line: 'football pitches of land cleared',
      sub: `With no licence to mine on the register. On average: ${num(unlicensedHa)} hectares in the 12 months leading up to ${dataDate}, seen by satellite in ${AREAS}.`,
    }),
  });
}

// What licence is on the cleared land, as one split bar. The two no-licence-to-mine labels are shown, and all
// licensed land is one grey remainder, unnamed
if (summary) {
  const totalHa = summary.total_ha;
  const part = (label: string, ha: number, share: number, alarm: boolean) => ({ label, ha: `${num(ha)} ha`, share, tiny: ha > 0 && share < 0.005, alarm });
  const nl = summary.by_licence['no licence'] ?? { ha: 0, share: 0 }, pr = summary.by_licence['prospecting only'] ?? { ha: 0, share: 0 };
  const rest = { ha: summary.total_ha - nl.ha - pr.ha, share: Math.max(0, 1 - nl.share - pr.share) };
  const parts = [part(LICENCE_SHORT['no licence'], nl.ha, nl.share, true), part(LICENCE_SHORT['prospecting only'], pr.ha, pr.share, true), part('Land with a licence (we leave it out)', rest.ha, rest.share, false)];
  const share = pct(summary.no_licence_to_mine.share);
  numberPosts.push({
    slug: 'licence',
    kind: 'Licence split',
    title: 'What licence is on the cleared land',
    alt: `A bar split by the licence on the cleared land. ${share} of it has no licence to mine: no licence at all, or only a licence to explore. ${parts.map((p) => `${p.label}: ${p.ha}`).join('. ')}.`,
    text: `${share} of the land cleared in the parts of Ghana's southern gold belt we track, in the last 12 months, has no licence to mine on it, going by the Minerals Commission's own register.

That is ${num(summary.no_licence_to_mine.ha)} hectares, seen by satellite.`,
    reply: `How we match each patch to the register: ${SITE}/method#licences`,
    render: () => licencePost({
      big: share,
      line: 'of the cleared land has no licence to mine',
      parts,
      sub: `No licence to mine means no licence at all, or only a licence to explore. From the Minerals Commission's public register, for the ${num(totalHa)} hectares cleared in the 12 months leading up to ${dataDate}.`,
    }),
  });
}

// District spotlight: one of the five districts with the most land cleared with no licence to mine, a different one
// each week, with its three largest pictured patches
const districtsReady = districtTotals.slice(0, 5)
  .map((d, rank) => ({ ...d, rank, inDistrict: photo.filter((p) => p.district === d.district).slice(0, 3) }))
  .filter((d) => d.inDistrict.length === 3);
if (districtsReady.length) {
  const d = pick(districtsReady);
  const name = tidyDistrict(d.district);
  const standing = d.rank === 0 ? 'the district with the most land cleared with no licence to mine' : `one of the ${count(Math.min(5, districtTotals.length))} districts with the most land cleared with no licence to mine`;
  numberPosts.push({
    slug: 'district',
    kind: 'District spotlight',
    title: `District spotlight: ${name}`,
    alt: `${num(d.ha)} hectares of land cleared with no licence to mine in 12 months in ${name}. Satellite pictures of its three largest patches with signs of mining: ${d.inDistrict.map((p) => placeName(p)).join(', ')}.`,
    text: `${name}: ${num(d.ha)} hectares of land cleared with no licence to mine in 12 months, about ${num(pitches(d.ha))} football pitches. It is ${standing} in the areas we track.

These are its three largest patches with signs of mining (open water, as in mining pits), seen by satellite.`,
    reply: `Every patch in ${name}, on the map: ${SITE}/map?district=${encodeURIComponent(d.district)}`,
    render: () => districtPost({
      title: `${name}, ${standing}`,
      big: `${num(d.ha)} ha`,
      line: `cleared in the 12 months leading up to ${dataDate}`,
      stat: `About ${num(pitches(d.ha))} football pitches`,
      places: d.inDistrict.map((p) => ({ label: `${hectares(p.ha)}, ${nearText(p) ?? 'unnamed place'}`, after: p.chips.after })),
    }),
  });
}

// Districts compared. A district is named only if some of its land shows signs of mining
const withSigns = new Set(active.filter(likelyLand).map((p) => p.district));
const byDistrict = districtTotals.filter((d) => withSigns.has(d.district)).slice(0, 8);
if (byDistrict.length >= 5) {
  numberPosts.push({
    slug: 'districts', kind: 'Districts compared', title: 'The districts with the most land cleared with no licence to mine',
    alt: `Bars for the ${count(byDistrict.length)} districts with the most land cleared with no licence to mine: ${byDistrict.map((d) => `${tidyDistrict(d.district)} ${num(d.ha)} hectares`).join(', ')}.`,
    text: `Land cleared with no licence to mine, in the 12 months leading up to ${dataDate}, by district:\n\n${byDistrict.map((d) => `${tidyDistrict(d.district)}: ${num(d.ha)} ha`).join('\n')}`,
    reply: `Every district, with its patches: ${SITE}/map`,
    render: () => barsPost({ title: 'Where the most land was cleared', line: `With no licence to mine, by district, in the 12 months leading up to ${dataDate}`, rows: byDistrict.map((d) => ({ label: tidyDistrict(d.district), value: d.ha, text: `${num(d.ha)} ha` })), sub: `From ${AREAS}.` }),
  });
}

// Patch sizes
if (unlicensed.length) {
  const bins = [[1, 2, '1 to 2 hectares'], [2, 5, '2 to 5 hectares'], [5, 10, '5 to 10 hectares'], [10, Infinity, '10 hectares or more']] as const;
  const rows = bins.map(([lo, hi, label]) => {
    const inBin = unlicensed.filter((p) => p.ha >= lo && p.ha < hi);
    const ha = inBin.reduce((t, p) => t + p.ha, 0);
    return { label, value: inBin.length, text: `${num(inBin.length)} patches, ${num(ha)} ha`, ha };
  });
  const all = rows.reduce((t, r) => t + r.ha, 0);
  const small = rows[0].value + rows[1].value;
  const tenths = Math.round((small / unlicensed.length) * 10);
  const smallHa = pct((rows[0].ha + rows[1].ha) / all);
  numberPosts.push({
    slug: 'sizes', kind: 'Patch sizes', title: 'Small patches, a lot of land',
    alt: `Bars showing how many patches with no licence to mine there are of each size: ${rows.map((r) => `${r.label}, ${r.text}`).join('. ')}.`,
    text: `${tenths} in 10 patches of cleared land with no licence to mine are under 5 hectares. Together they hold ${smallHa} of that land.\n\nNot a few huge pits. ${small >= 2000 ? 'Thousands of' : 'Many'} small ones, ${num(unlicensed.length)} patches in all.`,
    reply: `Every patch, on the map: ${SITE}/map`,
    render: () => barsPost({ title: 'How big the patches are', big: `${tenths} in 10`, line: `patches with no licence to mine are under 5 hectares. They hold ${smallHa} of that land.`, rows, sub: `${num(unlicensed.length)} patches of 1 hectare or more with no licence to mine, in the 12 months leading up to ${dataDate}.` }),
  });
}

// Where it is: every patch with no licence to mine as a dot
if (unlicensed.length) {
  numberPosts.push({
    slug: 'map', kind: 'Where it is', title: 'Every patch with no licence to mine, on one map',
    alt: `A map of southern Ghana with ${num(unlicensed.length)} pink dots, one for each patch of land cleared with no licence to mine, bigger dots for bigger patches.`,
    text: `Every dot is a patch of land cleared in the last 12 months where the register shows no licence to mine: ${num(unlicensed.length)} of them, across ${AREAS}.`,
    reply: `The map, where you can tap any dot: ${SITE}/map`,
    render: () => mapPost({ title: 'No licence to mine, one dot each', big: num(unlicensed.length), line: 'patches of land cleared in 12 months', sub: `Bigger dots are bigger patches. ${AREAS.charAt(0).toUpperCase() + AREAS.slice(1)}, in the 12 months leading up to ${dataDate}.`, frame: waterMap.frame, land: waterMap.land as number[][][][], dots: unlicensed.map((p) => ({ lon: p.lon, lat: p.lat, ha: p.ha })) }),
  });
}

// The water test: how many patches carry the Likely galamsey label, and what it means. The one post that uses the
// label's name, because it is the post that explains it
const likely = active.filter(likelyLand);
if (likely.length) {
  const ex = pick(photo.slice(0, 10), 3);
  numberPosts.push({
    slug: 'water-test', kind: 'The water test', title: 'The water test',
    alt: `${num(likely.length)} cleared patches labelled Likely galamsey.${ex ? ` A satellite picture of one, ${near(ex)}, with dark ponds on bare ground.` : ''}`,
    text: `${num(likely.length)} cleared patches with no licence to mine also show open water in or right beside them. Mining pits fill with water, so we take it as a sign of mining and label these patches Likely galamsey.\n\nIt is our guess from the satellite, not a finding. A patch without the label can still be galamsey.`,
    reply: `How the test works: ${SITE}/method#likely`,
    render: () => statPost({ title: 'The water test', big: num(likely.length), line: 'patches labelled Likely galamsey', body: 'No licence to mine on the register, and open water in or right beside the cleared land. Mining pits fill with water, so we take it as a sign of mining. It is our guess, not a finding.', picture: ex?.chips.after, caption: ex ? `One of them: ${hectares(ex.ha)} ${near(ex)}, ${shortDate(ex.chips.after.date)}` : undefined }),
  });
}

// Month in review: land with no licence to mine first seen in the last full month of data
if (reviewMonth?.inMonth.length) {
  const { start, inMonth, top } = reviewMonth;
  // The picture is the month's largest Likely galamsey patch. New patches often wait weeks for a cloud-free
  // picture, so fall back to the newest pictured one
  const shown = top ?? newest[0];
  const month = start.toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const ha = inMonth.reduce((t, p) => t + p.ha, 0);
  // The total is many patches spread over the areas, so say how small most are (only when it is true)
  const smallShare = inMonth.filter((p) => p.ha < 2).length / inMonth.length;
  const spread = `across the ${count(coverage.length)} areas we cover${smallShare > 0.5 ? ', most under 2 hectares' : ''}`;
  numberPosts.push({
    slug: 'month', kind: 'Month in review', title: `${month} in review`,
    alt: `${num(ha)} hectares of land with no licence to mine first seen cleared in ${month}, in ${num(inMonth.length)} patches ${spread}.${shown ? (top ? ` A satellite picture of one of them, the largest with signs of mining: ${hectares(shown.ha)} ${near(shown)}.` : ` A satellite picture of a recent patch with signs of mining: ${hectares(shown.ha)} ${near(shown)}.`) : ''}`,
    text: `In ${month}, satellites first saw ${num(ha)} hectares of newly cleared land with no licence to mine on the register, in ${num(inMonth.length)} patches ${spread}.${top ? `\n\nPictured: the largest of them with signs of mining (open water, as in mining pits), ${hectares(top.ha)} ${placeName(top)}.` : ''}\n\nNASA confirms clearing over several weeks, so this number can still go up.`,
    reply: `All patches, newest first: ${SITE}/map?sort=new`,
    render: () => statPost({ title: `${month} in review`, big: `${num(ha)} ha`, line: `newly cleared with no licence to mine, in ${num(inMonth.length)} patches ${spread}`, body: 'First seen by satellite that month. NASA confirms clearing over several weeks, so the number can still go up.', picture: shown?.chips.after, caption: shown ? `${top ? 'One of them, with signs of mining' : 'A recent patch with signs of mining'}: ${hectares(shown.ha)}, ${near(shown)}` : undefined }),
  });
}
