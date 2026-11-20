import fs from 'node:fs';
import { chromium } from '@playwright/test';
const root=process.argv[2];
if(!root)throw new Error('Pass absolute artifact root');
const summary=JSON.parse(fs.readFileSync(`${root}/site/summary.json`));
const browser=await chromium.launch({headless:true});
const checks=[];
try{
 for(const [name,viewport] of [['desktop',{width:1365,height:1000}],['mobile',{width:390,height:844}],['narrow-mobile',{width:320,height:844}]]){
  const context=await browser.newContext({viewport,offline:true});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`file://${root}/site/index.html`);
  await page.locator('.land path').waitFor({state:'visible'});
  if(await page.locator('.marker').count()!==11)throw new Error('Missing map marker');
  if(await page.locator('#walk-select option').count()!==11)throw new Error('Missing selectable walk');
  for(const walk of summary.walks){
   await page.locator('#walk-select').selectOption(walk.id);
   if(await page.locator('#selected-name').textContent()!==walk.name)throw new Error('Walk selection did not update');
   if((await page.locator('#record-count').textContent()).replaceAll(',','')!==String(walk.total))throw new Error('Wrong walk counts');
  }
  await page.locator('#walk-select').selectOption('milford-track');
  await page.locator('.month-bar').nth(3).click();
  if(await page.locator('#map-month').textContent()!=='April records')throw new Error('Month selection not reflected on map');
  await page.locator('#clear-month').click();
  await page.locator('#zoom-in').click();
  if((await page.evaluate(()=>window.fungiMap.getState())).zoom<=1)throw new Error('Zoom did not work');
  await page.locator('#zoom-reset').click();
  await page.locator('#walk-select').selectOption('abel-tasman-coast-track');
  const dimensions=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth,land:document.querySelector('.land').getBBox().width}));
  if(dimensions.scroll>dimensions.width)throw new Error('Horizontal overflow');
  if(dimensions.land<100)throw new Error('Blank or collapsed basemap');
  if(errors.length)throw new Error(JSON.stringify(errors));
  await page.screenshot({path:`${root}/qa/${name}.png`,fullPage:true});
  checks.push({viewport:name,all_walks_checked:11,month_selection:true,zoom:true,offline:true,page_errors:errors,dimensions});
  await context.close();
 }
 fs.writeFileSync(`${root}/qa/browser-receipt.json`,JSON.stringify({checks},null,2));
 console.log(JSON.stringify({checks},null,2));
}finally{await browser.close();}
