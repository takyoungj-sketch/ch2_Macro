import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import ts from 'typescript';
const source=await readFile(new URL('../src/utils/regionalTwinNotice.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {regionalTwinNotice:notice}=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
const base={loading:false,error:null,scopeEmpty:false,hasAnchor:false,hasTwins:false};
test('loading never announces empty results',()=>assert.equal(notice({...base,loading:true,scopeEmpty:true}),null));
test('known anchor shortage is distinct from a request failure',()=>{
 assert.equal(notice({...base,error:'이 읍면동의 아파트 재고로 쌍둥이 순위를 만들지 못했습니다. 거래와 핵심 변수가 있는 단지가 필요합니다.'}).kind,'insufficient');
 const failure=notice({...base,error:'DB 연결 오류'});assert.equal(failure.kind,'error');assert.equal(failure.reason,'DB 연결 오류');
});
test('no anchor and no candidate have different explanations',()=>{
 const scope=notice({...base,scopeEmpty:true});const candidates=notice({...base,hasAnchor:true});
 assert.equal(scope.kind,'insufficient');assert.equal(candidates.kind,'insufficient');assert.notEqual(scope.title,candidates.title);
});
test('successful candidate lists are preserved',()=>assert.equal(notice({...base,hasAnchor:true,hasTwins:true}),null));
