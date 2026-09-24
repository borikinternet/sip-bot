import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const workspaceDir='C:/devel/sip-bot';
const skillDir='C:/Users/dbori_4xv9zwb/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations';
const buildDir=path.join(workspaceDir,'artifacts/presentations/freeswitch-masterclass-build');
const finalPath=path.join(workspaceDir,'artifacts/presentations/freeswitch-masterclass-final/FreeSWITCH-call-center-masterclass-AC26.pptx');
const {finalizePresentation}=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const result=await finalizePresentation({
  workspaceDir,
  candidatePath:path.join(buildDir,'masterclass-draft.pptx'),
  finalPath,
  pythonExecutable:'C:/Users/dbori_4xv9zwb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
  integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
  requiredNativeTableOwnerSlides:[],
  requiredNativeChartOwnerSlides:[],
  fontPolicy:{
    basis:'reference',families:['Montserrat'],
    referencePath:'D:/Documents/Конференции/AsterConf.ru-2026/Запускаем call-center на FreeSWITCH.pptx',
    referenceSha256:'b286da98b703bb6d22b28aa7c09ccfd85edb2020a8ea77ec0ef480364b524907',
  },
  verifyArtifactToolImport:true,
  receiptPath:path.join(buildDir,'final-validation.json'),
});
console.log(JSON.stringify(result));
