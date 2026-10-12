// Copy the report figures used by the Insights page into public/figures before each build, so
// the static front end serves them itself (Vercel's web service has no FastAPI in front, D-019).
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "reports", "figures");
const dest = join(here, "..", "public", "figures");

if (!existsSync(src)) {
  console.log(`copy-figures: ${src} not found, keeping existing public/figures`);
} else {
  mkdirSync(dest, { recursive: true });
  const pngs = readdirSync(src).filter((f) => f.endsWith(".png"));
  for (const f of pngs) copyFileSync(join(src, f), join(dest, f));
  console.log(`copy-figures: ${pngs.length} figures -> public/figures`);
}
