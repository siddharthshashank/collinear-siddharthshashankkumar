// Render the editable SVGs with the pinned reviewer-only dependency.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'architecture-manifest.json'), 'utf8'));
(async () => {
  for (const name of manifest.figures) {
    await sharp(path.join(root, name + '.svg'), { density: 144 })
      .resize(2400, 1440)
      .png()
      .toFile(path.join(root, name + '.png'));
  }
  console.log('Rendered ' + manifest.figures.length + ' diagrams at 2400 × 1440.');
})().catch(error => { console.error(error); process.exit(1); });
