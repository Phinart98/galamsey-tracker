import fs from 'node:fs';
import path from 'node:path';

export function GET() {
  return new Response(fs.readFileSync(path.resolve(process.cwd(), '../../data/trend.json')), {
    headers: { 'Content-Type': 'application/json' },
  });
}
