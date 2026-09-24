import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const source = 'D:/Documents/Конференции/AsterConf.ru-2026/Запускаем call-center на FreeSWITCH.pptx';
const out = path.resolve('artifacts/presentations/freeswitch-masterclass-build/template-preview');
await fs.mkdir(out, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
console.log('slides', deck.slides.items.length);
for (let i = 0; i < deck.slides.items.length; i++) {
  const slide = deck.slides.getItem(i);
  const png = await slide.export({ format: 'png', scale: 1 });
  await fs.writeFile(path.join(out, `slide-${String(i+1).padStart(2,'0')}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(path.join(out, `slide-${String(i+1).padStart(2,'0')}.json`), await layout.text());
}
const inspection = await deck.inspect({ kind: 'slide,textbox,shape,image,layout', maxChars: 200000 });
await fs.writeFile(path.join(out,'inspect.ndjson'), inspection.ndjson);
const prior = await PresentationFile.importPptx(await FileBlob.load('D:/Documents/Конференции/AsterConf.ru-2026/SIP-ассистент-за-неделю_AC26-final-v3.pptx'));
for (const n of [1,10]) {
  const png = await prior.slides.getItem(n).export({format:'png',scale:1});
  await fs.writeFile(path.join(out,`prior-slide-${n+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
