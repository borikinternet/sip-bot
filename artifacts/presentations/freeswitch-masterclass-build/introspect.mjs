import { FileBlob, PresentationFile } from '@oai/artifact-tool';
const deck = await PresentationFile.importPptx(await FileBlob.load('D:/Documents/Конференции/AsterConf.ru-2026/Запускаем call-center на FreeSWITCH.pptx'));
const propNames = o => [...new Set([...Object.getOwnPropertyNames(o),...Object.getOwnPropertyNames(Object.getPrototypeOf(o) ?? {})])].sort();
console.log('slides',propNames(deck.slides));
const slide=deck.slides.getItem(2);
console.log('slide',propNames(slide));
console.log('shapes',propNames(slide.shapes));
console.log('shape count',slide.shapes.items.length);
console.log('first shape',propNames(slide.shapes.items[0]));
console.log('images',propNames(slide.images));
for (const n of [0,1,9,10]) {
  const s=deck.slides.getItem(n);
  console.log('\nSLIDE',n+1,'shapes',s.shapes.items.length,'images',s.images.items.length);
  for (const x of s.shapes.items) console.log(x.id,x.geometry,x.frame,JSON.stringify(x.text?.toString?.() ?? ''),x.text?.style);
  for (const x of s.images.items) console.log('image',x.id,x.frame,propNames(x).filter(k=>/delete|replace|frame/.test(k)));
}
