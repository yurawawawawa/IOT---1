/* Local broker + actual Python detector + 3 browser contexts.
   Sensor events below are explicitly synthetic TEST INPUT, never physical evidence. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const {spawn} = require('node:child_process');
const aedes = require('aedes')();
const {WebSocketServer,createWebSocketStream} = require('ws');
const {chromium} = require('playwright');
const root = path.resolve(__dirname,'..');
const listen = (server) => new Promise((resolve,reject) => {
  server.once('error',reject); server.listen(0,'127.0.0.1',() => resolve(server.address().port));
});
const delay = (ms) => new Promise((resolve) => setTimeout(resolve,ms));
async function waitFor(check,label,timeout=12000) {
  const start = Date.now();
  while (Date.now()-start < timeout) { if (await check()) return; await delay(100); }
  throw new Error('Timeout: '+label);
}

(async () => {
  const tcp = net.createServer(aedes.handle), websocketHttp = http.createServer();
  const websocket = new WebSocketServer({server:websocketHttp});
  websocket.on('connection',(socket) => aedes.handle(createWebSocketStream(socket)));
  let child, browser, logs = '', failure;
  const browserErrors = [];
  try {
    const tcpPort = await listen(tcp), wsPort = await listen(websocketHttp);
    const reserve = net.createServer(); const webPort = await listen(reserve);
    await new Promise((resolve) => reserve.close(resolve));
    const project = `test_${Date.now()}`, broker = `ws://127.0.0.1:${wsPort}/mqtt`;
    const python = process.env.BUDDYCHECK_PYTHON || path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
    child = spawn(python,['-u','detector.py'],{cwd:root,env:{...process.env,
      PROJECT_ID:project,MQTT_HOST:'127.0.0.1',MQTT_PORT:String(tcpPort),MQTT_TLS:'false',ALLOW_INSECURE_LOCAL:'true',
      MQTT_WS_URL:broker,MQTT_USERNAME:'',MQTT_PASSWORD:'',DASHBOARD_HOST:'127.0.0.1',DASHBOARD_PORT:String(webPort),
      STILL_SECONDS:'1',OBSERVATION_SECONDS:'6',REPLY_SECONDS:'2',CHECK_SECONDS:'8',COOLDOWN_SECONDS:'1',OFFLINE_SECONDS:'3',
    },windowsHide:true});
    child.stdout.on('data',(data) => logs+=data); child.stderr.on('data',(data) => logs+=data);
    child.on('error',(error) => logs+=error.message);
    const base = `http://127.0.0.1:${webPort}`;
    await waitFor(async () => { try { return (await fetch(base+'/config.json')).ok; } catch { return false; } },'Python HTTP server');
    const publicConfig = await (await fetch(base+'/config.json')).json();
    assert.equal(publicConfig.project_id,project);
    assert.ok(!('password' in publicConfig));
    assert.equal((await fetch(base+'/.env')).status,404);
    browser = await chromium.launch({headless:true});
    const dashboard = await browser.newPage({viewport:{width:1440,height:1100}});
    const phoneA = await browser.newPage({viewport:{width:390,height:844}});
    const phoneB = await browser.newPage({viewport:{width:390,height:844}});
    for (const page of [dashboard,phoneA,phoneB]) page.on('pageerror',(error) => browserErrors.push(error.message));
    const url = (view,role) => base+'/?'+new URLSearchParams({view,role,project,broker});
    await dashboard.goto(url('dashboard','edge1'));
    await dashboard.getByRole('button',{name:'Hubungkan dashboard'}).click();
    await waitFor(() => dashboard.locator('#detectorStatus').innerText().then((text) => text.includes('Detector aktif')),'detector heartbeat');
    fs.mkdirSync(path.join(root,'test-results'),{recursive:true});
    await dashboard.screenshot({path:path.join(root,'test-results/dashboard-empty.png'),fullPage:true});
    for (const [page,role] of [[phoneA,'edge1'],[phoneB,'edge2']]) {
      // Headless browsers have no physical motion sensor. Stub only the permission
      // boundary; the application still processes actual DeviceMotionEvent objects.
      await page.addInitScript(() => {
        Object.defineProperty(DeviceMotionEvent,'requestPermission',{value:async () => 'granted',configurable:true});
      });
      await page.goto(url('phone',role));
      await page.getByRole('button',{name:'Mulai sensor & hubungkan'}).click();
      await page.evaluate(() => {
        window.__testMotionKind='still';
        window.__testSensor = setInterval(() => {
          const impact = window.__testMotionKind==='impact';
          window.dispatchEvent(new DeviceMotionEvent('devicemotion',{
            accelerationIncludingGravity:{x:0,y:0,z:impact?24:9.81},
            rotationRate:{alpha:impact?120:0,beta:0,gamma:0},interval:50,
          }));
        },50);
      });
    }
    await waitFor(() => dashboard.locator('#pairCaption').innerText().then((text) => text==='2/2 perangkat aktif'),'two edge telemetry streams');
    console.log('PASS: two browser senders → local MQTT → Python detector → dashboard.');
    const incident = async (page) => {
      await page.evaluate(() => window.__testMotionKind='impact');
      await delay(1350);
      await page.evaluate(() => window.__testMotionKind='still');
    };
    await incident(phoneA);
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).waitFor();
    assert.equal(await phoneA.getByRole('button',{name:'REQUEST STATUS'}).count(),0);
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).click();
    await phoneA.getByRole('button',{name:"I'M SAFE"}).click();
    await waitFor(() => dashboard.locator('#events').innerText().then((text) => text.includes("I'M SAFE")),'safe reply');
    console.log('PASS: incident A → B requests → A answers SAFE → dashboard receives.');
    await delay(1100);
    await incident(phoneB);
    await phoneA.getByRole('button',{name:'REQUEST STATUS'}).click();
    await phoneB.getByRole('button',{name:'NEED HELP',exact:true}).click();
    await phoneA.getByRole('button',{name:'Sudah ditindaklanjuti'}).click();
    await waitFor(() => dashboard.locator('#events').innerText().then((text) => text.includes('Pengecekan selesai')),'need help acknowledgement');
    console.log('PASS: reverse roles, NEED HELP, and buddy acknowledgement.');
    await incident(phoneA);
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).click();
    await waitFor(() => phoneB.locator('#events').innerText().then((text) => text.includes('NO RESPONSE')),'reply timeout');
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).click();
    await phoneA.getByRole('button',{name:"I'M SAFE"}).click();
    await waitFor(() => dashboard.locator('#events h3').allTextContents().then((values) => values.filter((value)=>value==="I'M SAFE").length===2),'retry reply');
    console.log('PASS: NO RESPONSE timeout → request again → SAFE.');
    await phoneB.evaluate(() => clearInterval(window.__testSensor));
    await waitFor(() => dashboard.locator('#edge2-status').innerText().then((text) => text==='Offline'),'offline detection');
    await dashboard.getByRole('button',{name:'Jeda deteksi'}).click();
    await dashboard.getByRole('button',{name:'Lanjutkan deteksi'}).waitFor();
    const count = await dashboard.locator('.event-card').count();
    await incident(phoneA); await delay(3000);
    assert.equal(await dashboard.locator('.event-card').count(),count);
    console.log('PASS: missing sensor data becomes OFFLINE; paused detector does not open incidents.');
    for (const page of [dashboard,phoneA,phoneB]) {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth>innerWidth),false,'no horizontal overflow');
    }
    await dashboard.screenshot({path:path.join(root,'test-results/dashboard-flow.png'),fullPage:true});
    await phoneA.screenshot({path:path.join(root,'test-results/phone-flow.png'),fullPage:true});
    child.kill();
    await waitFor(() => dashboard.locator('#detectorStatus').innerText().then((text) => text.includes('offline')),'detector disconnect');
    assert.deepEqual(browserErrors,[]);
    console.log('PASS: desktop/mobile layouts, no browser exceptions, detector disconnect detected.');
    console.log('Integration complete. All sensor inputs were synthetic test events.');
  } catch (error) {
    failure = error; console.error(logs); console.error('Browser errors:',browserErrors);
    if (browser) {
      let index=0;
      for (const context of browser.contexts()) for (const page of context.pages()) {
        console.error('Page:',page.url(),(await page.locator('#notice').textContent().catch(()=>'')));
        await page.screenshot({path:path.join(root,`test-results/failure-${index++}.png`),fullPage:true}).catch(()=>{});
      }
    }
  }
  finally {
    if (browser) await browser.close();
    if (child && child.exitCode===null) child.kill();
    await new Promise((resolve) => aedes.close(resolve));
    for (const socket of websocket.clients) socket.terminate();
    await new Promise((resolve) => websocket.close(resolve));
    await new Promise((resolve) => websocketHttp.close(resolve));
    await new Promise((resolve) => tcp.close(resolve));
  }
  if (failure) throw failure;
})().catch((error) => { console.error(error); process.exitCode=1; });
