/* Visual QA for the existing BuddyCheck server. No synthetic sensor input. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({headless:true});
  const directory = path.resolve(__dirname,'../test-results');
  fs.mkdirSync(directory,{recursive:true});
  const failures = [];
  try {
    for (const [name,width,height,view] of [
      ['hiking-desktop',1440,1100,'dashboard'],
      ['hiking-phone',390,844,'phone'],
      ['hiking-small-phone',320,780,'phone'],
      ['hiking-tablet',768,1024,'dashboard'],
    ]) {
      const page = await browser.newPage({viewport:{width,height}});
      page.on('pageerror',(error) => failures.push(error.message));
      page.on('response',(response) => { if(response.status()>=400) failures.push(`${response.status()} ${response.url()}`); });
      await page.goto(`http://localhost:8000/?view=${view}`);
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({path:path.join(directory,name+'.png'),fullPage:true});
      const details = await page.evaluate(() => ({
        overflow:document.documentElement.scrollWidth>innerWidth,
        headingFont:getComputedStyle(document.querySelector('h1')).fontFamily,
        heroLoaded:document.querySelector('.hero-art').naturalWidth>0,
      }));
      if(details.overflow || !details.heroLoaded) failures.push(name+': '+JSON.stringify(details));
      console.log(name,JSON.stringify(details));
      await page.close();
    }
    if (failures.length) throw new Error(failures.join('\n'));
    console.log('Visual QA passed at desktop, tablet, and two phone widths.');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode=1; });
