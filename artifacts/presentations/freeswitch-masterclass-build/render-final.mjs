import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';
const source='C:/devel/sip-bot/artifacts/presentations/freeswitch-masterclass-final/FreeSWITCH-call-center-masterclass-AC26.pptx';
const out='C:/devel/sip-bot/artifacts/presentations/freeswitch-masterclass-build/final-preview';
await fs.mkdir(out,{recursive:true});
const deck=await PresentationFile.importPptx(await FileBlob.load(source));
for(let i=0;i<deck.slides.items.length;i++){
  const png=await deck.slides.getItem(i).export({format:'png',scale:1});
  await fs.writeFile(path.join(out,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(deck.slides.items.length);
