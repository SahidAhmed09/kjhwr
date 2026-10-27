// Copies the production build (frontend/dist) to <repo>/public, which Vercel serves from its CDN.
// Run through `npm run build:public`, which type-checks and builds first.
import { cpSync, existsSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, '../dist');
const target = resolve(here, '../../public');

if (!existsSync(resolve(dist, 'index.html'))) {
  throw new Error(`No build found at ${dist}. Run "npm run build" first.`);
}
rmSync(target, { recursive: true, force: true });
cpSync(dist, target, { recursive: true });
console.log(`Copied ${dist} -> ${target}`);
