import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/utils/regionalPredictionCategories.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {regionalPredictionCategories:normalize}=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
test('a loaded rare builder becomes the only model category',()=>{
 const original={builder_group:'현대건설',households:500,region_group:'지역 A'};
 assert.deepEqual(normalize(original,{builder_group:['기타']}),{...original,builder_group:'기타'});
 assert.equal(original.builder_group,'현대건설');
});
test('known categories are retained and rare structures follow the same rule',()=>{
 assert.deepEqual(normalize({builder_group:'현대건설',structure_group:'벽돌'},{builder_group:['현대건설','기타'],structure_group:['철콘','기타']}),{builder_group:'현대건설',structure_group:'기타'});
});
test('missing is kept separate from other, and unsupported categories are not invented',()=>{
 assert.equal(normalize({builder_group:'(미상)'},{builder_group:['미상','기타']}).builder_group,'미상');
 assert.equal(normalize({builder_group:'없는 업체'},{builder_group:['현대건설']}).builder_group,'없는 업체');
 assert.equal(normalize({builder_group:undefined},{builder_group:['기타']}).builder_group,undefined);
});
