const { chromium } = require('playwright');
(async()=>{
const fs = require('fs');
const [,, root, outdir, ...ids] = process.argv;
const css = fs.readFileSync(`${root}/project/deck.css`, 'utf8');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
for (const id of ids) {
  let sec = fs.readFileSync(`${root}/project/slides/${id}.html`, 'utf8').replace(/<aside>[\s\S]*?<\/aside>/, '');
  sec = sec.replace(/class="([^"]*)fragment/g, 'class="$1fragment visible');
  const html = `<!doctype html><html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..800&family=Lato:wght@300;400;700&family=JetBrains+Mono:wght@400;600&display=swap"><style>${css} *{animation:none!important;transition:none!important} body{margin:0} section{width:1920px;height:1080px;position:relative;overflow:hidden} x-icon{display:inline-block;border:4px solid currentColor;border-radius:50%;box-sizing:border-box} img{background:#333}</style></head><body>${sec}</body></html>`;
  await page.setContent(html, { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${outdir}/${id}.png` });
}
await browser.close();
})();
