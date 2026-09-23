const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const repo = process.env.TAWZEEVO_TOOL_ROOT || path.resolve(root, '../../..');
const req = createRequire(path.join(repo, 'package.json'));
const { ESLint } = req('eslint');
const js = req('@eslint/js');
const globals = req('globals');
(async()=>{
 const eslint=new ESLint({cwd:root,overrideConfigFile:true,overrideConfig:[
  {files:['app.js','entry.js'],...js.configs.recommended,languageOptions:{ecmaVersion:2022,globals:globals.browser}},
  {files:['**/*.cjs'],...js.configs.recommended,languageOptions:{ecmaVersion:2022,sourceType:'commonjs',globals:{...globals.node,...globals.browser}}}
 ]});
 const results=await eslint.lintFiles(['app.js','entry.js','serve.cjs','tests/*.cjs']);
 console.log((await eslint.loadFormatter('stylish')).format(results));
 if(results.some(r=>r.errorCount||r.warningCount))process.exitCode=1;
 else console.log('Prototype ESLint: PASS');
})();
