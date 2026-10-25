import { lead, summary, where } from '../../lib/data';
import { homeCard } from '../../lib/og';
import { num, pct } from '../../lib/format';

export async function GET() {
  const card = await homeCard({
    line: summary ? `${num(summary.total_ha)} hectares of land cleared in 12 months ${where}` : 'Galamsey Tracker',
    sub: summary ? `${pct(summary.no_licence_to_mine.share)} of it has no licence to mine. Satellite evidence, updated every week.` : 'Satellite evidence, updated every week.',
    before: lead?.chips.before,
    after: lead?.chips.after,
  });
  return new Response(new Uint8Array(card), { headers: { 'Content-Type': 'image/png' } });
}
