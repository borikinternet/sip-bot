import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const source = 'D:/Documents/Конференции/AsterConf.ru-2026/Запускаем call-center на FreeSWITCH.pptx';
const root = path.resolve('artifacts/presentations/freeswitch-masterclass-build');
const draft = path.join(root, 'masterclass-draft.pptx');
const previewDir = path.join(root, 'draft-preview');
await fs.mkdir(previewDir, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
if (deck.slides.items.length !== 11) throw new Error('Unexpected source slide count');

const W='#FFFFFF', Y='#FFC52E', R='#FF5146', PANEL='#563B36', PANEL2='#6B423A';
function shape(slide, name, text, x,y,w,h,size=28, color=W, bold=false, align='left') {
  const s=slide.shapes.add({
    geometry:'textbox', name,
    position:{left:x,top:y,width:w,height:h},
    fill:'none', line:{fill:'none',width:0},
  });
  s.text=text;
  s.text.style={typeface:'Montserrat',fontSize:size,color,bold,
    alignment:align,verticalAlignment:'middle',autoFit:'shrinkText',wrap:'word'};
  return s;
}
function panel(slide,name,x,y,w,h,fill=PANEL) {
  return slide.shapes.add({geometry:'roundRect',name,
    position:{left:x,top:y,width:w,height:h},fill,
    line:{fill:'#96665B',width:1.5},borderRadius:12});
}
function line(slide,x,y,w,color=R,h=6) {
  return slide.shapes.add({geometry:'rect',name:'accent-line',
    position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:'none',width:0}});
}
function resetMiddle(slide,title,time) {
  slide.shapes.deleteAll();
  for (const im of [...slide.images.items]) im.delete();
  shape(slide,'title',title,45,55,1160,77,46,W,true);
  line(slide,80,138,78);
  shape(slide,'time',time,1030,62,200,48,22,Y,true,'right');
}
function notes(slide,text) {slide.speakerNotes.textFrame.setText(text);}

// Mandatory title slide: preserve conference artwork and title placement.
{
  const s=deck.slides.getItem(0);
  s.shapes.items[0].text='Запускаем call-center\nна FreeSWITCH';
  notes(s,'Открытие. За 60 минут с вопросами собираем учебный call-center. Ведущий и автономный агент работают с двумя чистыми Debian 12 WSL-инстансами на одной Windows-машине. На занятии исполняем подготовленную карту 019, сейчас её не запускать.');
}

// Mandatory problem/speaker slide: same spatial structure and sections.
{
  const s=deck.slides.getItem(1);
  const byId=Object.fromEntries(s.shapes.items.map(x=>[String(x.id),x]));
  byId['5'].text='Проблематика мастер-класса:';
  byId['4'].text='Соберём работающий call-center с нуля: FreeSWITCH, два SIP-телефона и очередь оператора.\nОдинаковую задачу параллельно решают ведущий и автономный агент — в разных WSL-инстансах.\nКритерий результата: вызов проходит в очередь, оператор отвечает, голос слышен в обе стороны.';
  byId['7'].text='Борисов\nДмитрий';
  byId['8'].text='Разработчик';
  byId['9'].text='Вольный торговец';
  byId['10'].text='25 лет в телекоме.\nОт интеграции до разработки сетевых платформ.';
  shape(s,'speaker-initials','ДБ',117,145,140,125,70,'#4B2F2C',true,'center');
  notes(s,'Пояснить, что это демонстрация работы, не доклад о готовом продукте. Два независимых чистых Debian 12 WSL2 на одном Windows-хосте. Подготовительный срез 019-A делается до начала часа: одинаковый rootfs и базовый systemd, но FreeSWITCH и учебный конфиг ещё не установлены. В сетевом пространстве WSL слушающие порты могут конфликтовать: подготовка параллельна, живые проверки идут по очереди.');
}

// 3. The call path. This is the diagram to return to during the live steps.
{
  const s=deck.slides.getItem(2);resetMiddle(s,'Что собираем','0–5 мин');
  panel(s,'caller',62,205,290,138); panel(s,'pbx',493,205,294,138,PANEL2); panel(s,'operator',928,205,290,138);
  shape(s,'caller-text','MicroSIP\n1000 · звонящий',82,220,250,108,28,W,true,'center');
  shape(s,'pbx-text','FreeSWITCH\nSIP + RTP',513,220,254,108,30,W,true,'center');
  shape(s,'operator-text','MicroSIP\n1001 · оператор',948,220,250,108,28,W,true,'center');
  shape(s,'arrow-1','→',383,240,74,68,48,Y,true,'center');
  shape(s,'arrow-2','→',820,240,74,68,48,Y,true,'center');
  panel(s,'routes',62,405,1156,206,'#4E312D');
  shape(s,'route-1','1000 → 1001   прямой вызов',96,425,1040,53,29,W,true);
  shape(s,'route-2','1000 → 7000   очередь support@default → оператор 1001',96,486,1070,52,29,W,true);
  shape(s,'route-3','7100 → science-bot@default → 1002   подготовим, подключим позже',96,544,1070,48,23,Y,false);
  notes(s,'Показать различие: 1000/1001/1002 — SIP-учётки, 7000/7100 — номера dialplan, support@default и science-bot@default — имена очередей. Во втором мастер-классе к 1002 подключим односессионного SIP-бота, но сейчас не выдавать конфигурацию за живой бот-звонок.');
}

// 4. Two WSL lanes and stage boundary.
{
  const s=deck.slides.getItem(3);resetMiddle(s,'Две дорожки, один результат','до старта');
  panel(s,'human',64,200,548,286); panel(s,'agent',668,200,548,286);
  shape(s,'human-label','Ведущий',99,220,480,55,34,Y,true);
  shape(s,'human-list','Debian-FS-Human\nНастройка вручную на экране\nMicroSIP-пара H',99,286,480,151,27,W,false);
  shape(s,'agent-label','Агент без контекста',703,220,480,55,34,Y,true);
  shape(s,'agent-list','Debian-FS-Agent\nТа же карта 019 и критерии\nMicroSIP-пара A',703,286,480,151,27,W,false);
  shape(s,'condition','Параллельны подготовка и конфиги; SIP/RTP-проверки — по очереди.',86,531,1105,76,27,W,true,'center');
  notes(s,'Перед занятием: 019-A, два свежих Debian 12 WSL-инстанса на одном Windows-хосте; ≥20 GiB на каждый; rootfs и пакеты разрешено заранее скачать и проверить SHA-256. Не выполнять Map-019 до конференции. Во время занятия команды агенту выдаются по самодостаточной карте, без истории этого чата. Не перезаписывать чужие WSL-дистрибутивы, не выполнять wsl --shutdown, не трогать Docker. Из-за общего network namespace установка пакетов, если postinst запускает службу, и live gates координируются ведущим. Время ожидания окна не входит в активное время сравнения.');
}

// 5. Installation; command prompts stay short on slide, full recipe in notes/runbook.
{
  const s=deck.slides.getItem(4);resetMiddle(s,'Ставим FreeSWITCH','5–15 мин');
  panel(s,'repo',62,201,1156,98);panel(s,'packages',62,319,1156,98);panel(s,'service',62,437,1156,98);
  shape(s,'step1','1   Подписанный Bookworm-репозиторий   fi.itlnk.ru/freeswitch',93,220,1090,60,29,W,true);
  shape(s,'step2','2   freeswitch-meta-vanilla  +  freeswitch-mod-callcenter  +  systemd',93,338,1090,60,28,W,true);
  shape(s,'step3','3   systemctl enable --now freeswitch   →   fs_cli -x status',93,456,1090,60,28,W,true);
  shape(s,'guard','Пакет установлен ≠ модуль загружен ≠ очередь настроена',93,582,1090,55,27,Y,true,'center');
  notes(s,'В root shell Debian добавить deb [signed-by=/usr/share/keyrings/freeswitch-packaging.gpg] http://fi.itlnk.ru/freeswitch bookworm main. Сверить fingerprint ключа 655DA1341B5207915210AFE936B4249FA7B0FB03. apt-get update; apt-cache policy freeswitch freeswitch-mod-callcenter; DEBIAN_FRONTEND=noninteractive apt-get install -y freeswitch-meta-vanilla freeswitch-mod-callcenter freeswitch-systemd; systemctl enable --now freeswitch; systemctl is-active freeswitch; fs_cli -x status. Не использовать trusted=yes. Показать, откуда взяты пакеты. Полные команды — docs/workshops/freeswitch-callcenter-masterclass.md, раздел 2.');
}

// 6. Direct call first, to isolate basic SIP/RTP from callcenter.
{
  const s=deck.slides.getItem(5);resetMiddle(s,'Сначала SIP и звук','15–25 мин');
  panel(s,'left',63,200,551,335); panel(s,'right',665,200,551,335);
  shape(s,'registered','REGISTER',94,223,480,51,35,Y,true);
  shape(s,'reg-body','1000 и 1001 в разных portable MicroSIP\nОдин адрес WSL, разные локальные SIP/RTP-порты',94,285,480,154,26,W);
  shape(s,'reg-cli','sofia status profile internal reg',94,468,480,44,24,Y,true);
  shape(s,'direct','ПРЯМОЙ ВЫЗОВ',696,223,480,51,35,Y,true);
  shape(s,'direct-body','1000 → 1001 → ответ\nФраза слышна в обе стороны\nПроверяем две ноги и PCMU',696,285,480,154,26,W);
  shape(s,'direct-cli','fs_cli -x "show channels"',696,468,480,44,24,Y,true);
  shape(s,'why','Если прямой вызов не работает — очереди пока не трогаем.',93,579,1080,57,27,W,true,'center');
  notes(s,'Две portable MicroSIP-копии в независимых каталогах Windows. Учётки 1000/1001, пароль из vars.xml default_password (учебный Workshop-2026!), сервер IPv4 Debian:5060, UDP, PCMU/8000. Для двух копий — sourcePort 5062/5064, RTP ranges 40000–40100 и 40200–40300. Проверить регистрацию, затем прямой вызов 1000→1001, ответить, произнести фразу, показать show channels и слышимость в обе стороны. На одном компьютере использовать гарнитуру/mute для предотвращения акустической обратной связи. При проблемах со звуком проверить SIP-IP/RTP-IP/Ext-* через sofia status profile internal, выключить STUN в учебной LAN-конфигурации и запускать FreeSWITCH с -nonat -nonatmap, как в сценарии.');
}

// 7. Callcenter configuration and the two independent queues.
{
  const s=deck.slides.getItem(6);resetMiddle(s,'Очередь — это цепочка связей','25–40 мин');
  shape(s,'chain','номер → dialplan → queue → tier → agent → SIP-контакт',71,191,1130,72,29,Y,true,'center');
  panel(s,'support',65,299,1150,121);
  shape(s,'support-route','7000 → support@default → 1001@default → user/1001@$${domain}',89,322,1100,72,27,W,true);
  panel(s,'bot',65,444,1150,121);
  shape(s,'bot-route','7100 → science-bot@default → 1002@default → user/1002@$${domain}',89,467,1100,72,27,W,true);
  shape(s,'check','modules.conf.xml  •  callcenter.conf.xml  •  dialplan/default/20_workshop_callcenter.xml',71,608,1130,53,22,W,false,'center');
  notes(s,'В modules.conf.xml раскомментировать <load module="mod_callcenter"/>. В callcenter.conf.xml руками показать очереди, агентов callback и tier; tier связывает конкретного агента с очередью. Для оператора contact=[leg_timeout=15]user/1001@$${domain}; буквальное user/1001@default ранее приводило к SUBSCRIBER_ABSENT. Для бота contact с absolute_codec_string=PCMU. Dialplan extension 7000 выполняет answer и callcenter support@default, 7100 — answer, запись стерео и callcenter science-bot@default. Рестарт сервиса; module_exists mod_callcenter, callcenter_config queue list, agent list, tier list. Подчеркнуть, что 1002 здесь только подготовлен и ещё не зарегистрирован.');
}

// 8. Observable live gate.
{
  const s=deck.slides.getItem(7);resetMiddle(s,'Живой gate: звонок на 7000','40–50 мин');
  const xs=[64,366,668,970];
  const names=['Набрать','Подождать','Ответить','Проверить'];
  const desc=['1000 → 7000','Очередь\nвидит вызов','MicroSIP 1001\nподнимает трубку','Двусторонний голос\nи PCMU'];
  for(let i=0;i<4;i++){
    panel(s,`stage-${i}`,xs[i],226,250,232,i%2?PANEL2:PANEL);
    shape(s,`stage-title-${i}`,names[i],xs[i]+18,248,215,55,30,Y,true,'center');
    shape(s,`stage-body-${i}`,desc[i],xs[i]+18,322,215,104,25,W,false,'center');
    if(i<3) shape(s,`arr-${i}`,'→',xs[i]+254,312,44,61,38,Y,true,'center');
  }
  shape(s,'evidence','queue members  •  agent list  •  show channels  •  слышимость',91,535,1100,71,28,W,true,'center');
  notes(s,'Звонок 1000→7000. До ответа показать callcenter_config queue list members support@default, callcenter_config agent list 1001@default, show channels: waiting/trying, слышно удержание. На 1001 ответить, убедиться в двустороннем PCMU-звуке, показать answered/in a queue call. 7100 не выдавать за звонок к работающему боту: 1002 подключим на следующем мастер-классе. Если очередной вызов не проходит, не маскировать это статусом fs_cli: пройти цепь module→queue→agent/tier→dialplan→SIP registration→RTP.');
}

// 9. Compare the two lanes and connect to the second masterclass.
{
  const s=deck.slides.getItem(8);resetMiddle(s,'Сравниваем результат, не лозунги','50–55 мин');
  panel(s,'comparison',64,202,1152,291);
  shape(s,'header','Критерии одинаковы',100,222,1060,61,35,Y,true,'center');
  shape(s,'check-list','Служба активна   •   2 регистрации   •   прямой PCMU-звонок\n2 очереди + 2 агента + 2 tier   •   7000 answered + звук',104,308,1050,125,27,W,true,'center');
  shape(s,'metric','Считаем активное время отдельно от ожидания SIP-окна.',90,522,1100,62,28,W,true,'center');
  shape(s,'next','Далее: подключим бота 1002, загрузим RAG и проверим 7100 → 7000.',90,592,1100,68,24,Y,false,'center');
  notes(s,'Ведущий проверяет агентский стенд независимо от самоотчёта: fs_cli, регистрации, прямой разговор и слышимость, queue state, 7000. Ожидание сетевого окна не считать активной работой. Если в одном стенде красный gate — не объявлять победу другого вместо исправления. После занятия второй мастер-класс подключит SIP-ассистента к 1002, обучит его по документам через RAG, проверит второй одновременный вызов и перевод к человеку на 7000.');
}

// Mandatory two-column conclusions: keep the title and two text columns.
{
  const s=deck.slides.getItem(9);
  const byId=Object.fromEntries(s.shapes.items.map(x=>[String(x.id),x]));
  byId['2'].text='Итоги';
  byId['3'].delete();byId['4'].delete();
  const left=['Подписанные пакеты Debian 12','Две регистрации и прямой звонок','7000 → support → 1001','7100 готова для бота'];
  const right=['Queue ≠ agent ≠ tier','Приёмка: состояние + звук','Две WSL-дорожки, один gate','Далее: бот 1002 + RAG'];
  for(let i=0;i<4;i++){
    const y=207+i*105;
    shape(s,`bullet-left-${i}`,'•',113,y,31,63,31,Y,true);
    shape(s,`outcome-left-${i}`,left[i],155,y,472,72,26,W,i===2);
    shape(s,`bullet-right-${i}`,'•',666,y,31,63,31,Y,true);
    shape(s,`outcome-right-${i}`,right[i],708,y,470,72,26,W,i===3);
  }
  notes(s,'Это ожидаемый итог занятия, не отчёт о заранее проведённом прогоне. Перед показом сверить фактический результат: active/enabled, две регистрации, прямой двусторонний звук, mod_callcenter true, обе очереди/агента/tier, answered 7000 и звук. На 7100 не обещать живой бот-сценарий сегодня. При срыве live gate честно назвать незакрытую проверку и место ошибки.');
}

// Mandatory closing/contact slide: preserve title, subtitle, contact block and QR slot.
{
  const s=deck.slides.getItem(10);
  const byId=Object.fromEntries(s.shapes.items.map(x=>[String(x.id),x]));
  byId['4'].text='Спасибо за внимание!';
  byId['6'].text='Буду рад ответить на вопросы сейчас или после мастер-класса:';
  byId['5'].delete();
  shape(s,'speaker-name','Борисов Дмитрий',347,377,450,51,25,W,true);
  shape(s,'speaker-email','dborisov@mail.ru',347,426,450,46,25,W);
  shape(s,'speaker-phone','+7 905 723-97-18',347,473,450,46,25,W);
  shape(s,'speaker-telegram','t.me/borikbobrujskov',347,520,490,46,25,W);
  try {
    const url='https://api.qrserver.com/v1/create-qr-code/?size=240x240&data='+encodeURIComponent('https://t.me/borikbobrujskov');
    const response=await fetch(url);
    if(!response.ok) throw new Error(`QR HTTP ${response.status}`);
    const bytes=new Uint8Array(await response.arrayBuffer());
    s.images.items[0].replace({blob:bytes,contentType:'image/png',alt:'Telegram Дмитрия Борисова'});
  } catch(e) { throw new Error(`Cannot replace obsolete QR: ${e}`); }
  notes(s,'QR ведёт на https://t.me/borikbobrujskov. Вопросы по настройке FreeSWITCH и следующий мастер-класс по SIP-ассистенту/RAG. Контакты взяты из ранее подготовленного доклада этого же спикера, не из шаблонной заглушки.');
}

await (await PresentationFile.exportPptx(deck)).save(draft);
for(let i=0;i<deck.slides.items.length;i++){
  const png=await deck.slides.getItem(i).export({format:'png',scale:1});
  await fs.writeFile(path.join(previewDir,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(draft);
