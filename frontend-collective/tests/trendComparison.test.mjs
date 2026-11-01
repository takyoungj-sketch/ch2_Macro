import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source = await readFile(new URL('../src/utils/trendComparison.ts', import.meta.url),'utf8');
const {outputText} = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {loadYearlyComparisons,trendAxisOrders,consecutiveTrendSegments} = await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
test('one failed comparison preserves successful series and names the failure',async()=>{
 const targets=[{key:'ok',label:'비교 분양권 A'},{key:'fail',label:'비교 분양권 B'}];
 const result=await loadYearlyComparisons(targets,async key=>{if(key==='fail')throw Error('failure');return {building_key:key,points:[{year:2016,count:10,mean:100}],display_name:'raw'};});
 assert.deepEqual(result.failed,['비교 분양권 B']);
 assert.equal(result.series.length,1);
 assert.equal(result.series[0].display_name,'비교 분양권 A');
 assert.deepEqual(result.series[0].points,[{year:2016,count:10,mean:100}]);
});
test('all failed comparisons return no fabricated data',async()=>{
 const result=await loadYearlyComparisons([{key:'bad',label:'실패 대상'}],async()=>{throw Error('failure')});
 assert.deepEqual(result,{series:[],failed:['실패 대상']});
});
test('annual axis preserves missing years without adding data points',()=>{
 assert.deepEqual(trendAxisOrders([2024,2018,2023],true),[2018,2019,2020,2021,2022,2023,2024]);
 assert.deepEqual(trendAxisOrders([2,4],false),[2,4]);
});
test('discontinuous observations are never joined by one line',()=>{
 const points=[{xOrder:2024,value:140},{xOrder:2018,value:100},{xOrder:2023,value:130}];
 assert.deepEqual(consecutiveTrendSegments(points).map(group=>group.map(p=>p.xOrder)),[[2018],[2023,2024]]);
 assert.deepEqual(points.map(p=>p.xOrder),[2024,2018,2023]);
});
