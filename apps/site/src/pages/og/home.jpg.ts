import { doorstep, summary, townsNear, where } from '../../lib/data';
import { homeCard } from '../../lib/og';
import { num, pct } from '../../lib/format';
import { WEEKLY } from '../../lib/site';

const lead = doorstep(1)[0]?.place;

export async function GET() {
  const card = await homeCard({
    line: townsNear ? `At least ${num(townsNear.count)} towns and villages have land cleared within a kilometre of them` : summary ? `${num(summary.total_ha)} hectares of land cleared in 12 months ${where}` : 'Galamsey Tracker',
    sub: summary ? `${num(summary.total_ha)} hectares in 12 months, ${pct(summary.no_licence_to_mine.share)} of it with no licence to mine.` : WEEKLY ? 'Satellite evidence, updated every week.' : 'Satellite evidence of cleared land.',
    before: lead?.chips.before,
    after: lead?.chips.after,
  });
  return new Response(new Uint8Array(card), { headers: { 'Content-Type': 'image/jpeg' } });
}
