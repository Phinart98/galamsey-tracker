import fs from 'node:fs';
import path from 'node:path';

export function GET() {
  return new Response(fs.readFileSync(path.resolve(process.cwd(), '../../data/summary/latest.json')), {
    headers: { 'Content-Type': 'application/json' },
  });
}
