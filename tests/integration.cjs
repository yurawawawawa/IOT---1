/* Local broker + actual Python detector + two phone and two dashboard contexts.
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
const mqtt = require('mqtt');
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
  let child, browser, logs = '', failure, roomClient, roomPulse;
  const browserErrors = [];
  try {
    const tcpPort = await listen(tcp), wsPort = await listen(websocketHttp);
    const reserve = net.createServer(); const webPort = await listen(reserve);
    await new Promise((resolve) => reserve.close(resolve));
    const project = `test_${Date.now()}`, otherProject = `other_${Date.now()}`, defaultProject = 'default_only';
    const broker = `ws://127.0.0.1:${wsPort}/mqtt`;
    const python = process.env.BUDDYCHECK_PYTHON || path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
    child = spawn(python,['-u','detector.py'],{cwd:root,env:{...process.env,
      PROJECT_ID:defaultProject,MQTT_HOST:'127.0.0.1',MQTT_PORT:String(tcpPort),MQTT_TLS:'false',ALLOW_INSECURE_LOCAL:'true',
      MQTT_WS_URL:broker,MQTT_USERNAME:'',MQTT_PASSWORD:'',DASHBOARD_HOST:'127.0.0.1',DASHBOARD_PORT:String(webPort),
      STILL_SECONDS:'1',OBSERVATION_SECONDS:'6',REPLY_SECONDS:'4',CHECK_SECONDS:'8',COOLDOWN_SECONDS:'1',OFFLINE_SECONDS:'3',
    },windowsHide:true});
    child.stdout.on('data',(data) => logs+=data); child.stderr.on('data',(data) => logs+=data);
    child.on('error',(error) => logs+=error.message);
    const base = `http://127.0.0.1:${webPort}`;
    await waitFor(async () => { try { return (await fetch(base+'/config.json')).ok; } catch { return false; } },'Python HTTP server');
    const publicConfig = await (await fetch(base+'/config.json')).json();
    assert.equal(publicConfig.project_id,defaultProject);
    assert.equal(publicConfig.room_mode,'multi');
    assert.ok(!('password' in publicConfig));
    assert.equal((await fetch(base+'/.env')).status,404);
    browser = await chromium.launch({headless:true});
    const dashboard = await browser.newPage({viewport:{width:1440,height:1100}});
    const phoneA = await browser.newPage({viewport:{width:390,height:844}});
    const phoneB = await browser.newPage({viewport:{width:390,height:844}});
    const otherDashboard = await browser.newPage({viewport:{width:1000,height:1000}});
    for (const page of [dashboard,phoneA,phoneB,otherDashboard]) page.on('pageerror',(error) => browserErrors.push(error.message));
    const url = (view,role) => base+'/?'+new URLSearchParams({view,role,project,broker});
    await dashboard.goto(url('dashboard','edge1'));
    await dashboard.getByRole('button',{name:'Hubungkan dashboard'}).click();
    await waitFor(() => dashboard.locator('#detectorStatus').innerText().then((text) => text.includes('Detector aktif')),'detector heartbeat');
    assert.ok((await dashboard.locator('#roomSummary').innerText()).includes(project));
    await otherDashboard.goto(base+'/?'+new URLSearchParams({view:'dashboard',project:otherProject,broker}));
    await otherDashboard.getByRole('button',{name:'Hubungkan dashboard'}).click();
    await waitFor(() => otherDashboard.locator('#detectorStatus').innerText().then((text) => text.includes('Detector aktif')),'other room created without changing env');
    const otherStates = [], otherReceipts = new Map();
    roomClient = mqtt.connect(`mqtt://127.0.0.1:${tcpPort}`,{reconnectPeriod:0});
    roomClient.on('message',(address,bytes) => {
      const value=JSON.parse(bytes.toString());
      if(address.endsWith('/state')) otherStates.push(value);
      else otherReceipts.set(value.command_id,value);
    });
    await new Promise((resolve,reject) => {
      roomClient.once('error',reject);
      roomClient.once('connect',() => roomClient.subscribe([`buddycheck/${otherProject}/state`,`buddycheck/${otherProject}/receipts/edge2`,`buddycheck/${otherProject}/receipts/edge1`],{qos:1},(error) => error?reject(error):resolve()));
    });
    let otherSequence=0, otherImpact=false;
    const publishOtherRoom = () => {
      for (const device of ['edge1','edge2']) {
        const impact = device==='edge1' && otherImpact;
        roomClient.publish(`buddycheck/${otherProject}/edge/${device}/telemetry`,JSON.stringify({
          device_id:device,boot_id:'other_room_test',sequence:otherSequence,sent_at_ms:Date.now(),
          motion_rms:impact?10:0.1,rotation_rad:impact?0.8:0.01,accel_peak:impact?14:0.2,
          window_ms:1000,sample_count:20,source:'simulator',
        }),{qos:1,retain:false});
      }
      otherSequence++;
    };
    publishOtherRoom(); roomPulse=setInterval(publishOtherRoom,1000);
    await waitFor(() => otherDashboard.locator('#pairCaption').innerText().then((text) => text==='2/2 perangkat aktif'),'second independent pair');
    fs.mkdirSync(path.join(root,'test-results'),{recursive:true});
    await dashboard.screenshot({path:path.join(root,'test-results/dashboard-empty.png'),fullPage:true});
    for (const [page,role] of [[phoneA,'edge1'],[phoneB,'edge2']]) {
      // Headless browsers have no physical motion sensor. Stub only the permission
      // boundary; the application still processes actual DeviceMotionEvent objects.
      await page.addInitScript(() => {
        Object.defineProperty(DeviceMotionEvent,'requestPermission',{value:async () => 'granted',configurable:true});
      });
      await page.addInitScript((role) => {
        window.__testVibrations=[];
        // Simulate an Android-style vibration API on A and no vibration API on B.
        // This checks API calls and fallback UI, not a physical vibration motor.
        Object.defineProperty(navigator,'vibrate',{configurable:true,value:role==='edge1' ? (pattern) => {
          window.__testVibrations.push(pattern); return true;
        } : undefined});
      },role);
      await page.goto(url('phone',role));
      await page.getByRole('button',{name:'Tes bunyi & getar'}).click();
      if(role==='edge2') assert.ok((await page.locator('#notificationStatus').innerText()).includes('Getar tidak tersedia'));
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
    console.log('PASS: two arbitrary group IDs work simultaneously while .env keeps a different default ID.');
    const incident = async (page) => {
      await page.evaluate(() => window.__testMotionKind='impact');
      await delay(1350);
      await page.evaluate(() => window.__testMotionKind='still');
    };
    await incident(phoneA);
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).waitFor();
    assert.equal(await phoneA.getByRole('button',{name:'REQUEST STATUS'}).count(),0);
    assert.equal(await otherDashboard.locator('.event-card').count(),0,'events from the primary room must not appear in another room');
    const primaryEventId=await phoneB.locator('.event-card').getAttribute('data-event-id');
    roomClient.publish(`buddycheck/${otherProject}/commands/edge2`,JSON.stringify({command_id:'cross_room_attempt',action:'REQUEST_STATUS',actor:'edge2',event_id:primaryEventId,sent_at_ms:Date.now()}),{qos:1});
    await waitFor(() => otherReceipts.has('cross_room_attempt'),'cross-room rejection');
    assert.equal(otherReceipts.get('cross_room_attempt').ok,false);
    assert.ok((await phoneB.locator('#events').innerText()).includes('CHECK YOUR BUDDY'));
    const requestsBefore = await phoneA.evaluate(() => window.__testVibrations.filter((pattern) => Array.isArray(pattern) && pattern[0]===350).length);
    await phoneB.getByRole('button',{name:'REQUEST STATUS'}).click();
    await phoneA.locator('#incomingRequest').waitFor({state:'visible'});
    await waitFor(() => phoneA.evaluate((before) => window.__testVibrations.filter((pattern) => Array.isArray(pattern) && pattern[0]===350).length===before+1,requestsBefore),'incoming request vibration');
    await delay(1050);
    assert.equal(await phoneA.evaluate(() => window.__testVibrations.filter((pattern) => Array.isArray(pattern) && pattern[0]===350).length),requestsBefore+1,'heartbeat must not replay vibration');
    await phoneA.screenshot({path:path.join(root,'test-results/incoming-request.png'),fullPage:true});
    await phoneA.getByRole('button',{name:'Lihat permintaan'}).click();
    await phoneA.getByRole('button',{name:"I'M SAFE"}).click();
    await phoneA.locator('#incomingRequest').waitFor({state:'hidden'});
    await waitFor(() => dashboard.locator('#events').innerText().then((text) => text.includes("I'M SAFE")),'safe reply');
    console.log('PASS: incident A → B requests → A answers SAFE → dashboard receives.');
    otherImpact=true; await delay(1350); otherImpact=false;
    await waitFor(() => otherStates.some((value) => value.events?.some((event) => event.status==='CHECK_BUDDY')),'incident in second room');
    const otherEvent=otherStates.at(-1).events.at(-1);
    roomClient.publish(`buddycheck/${otherProject}/commands/edge2`,JSON.stringify({command_id:'other_request',action:'REQUEST_STATUS',actor:'edge2',event_id:otherEvent.event_id,sent_at_ms:Date.now()}),{qos:1});
    await waitFor(() => otherReceipts.has('other_request'),'second room request');
    assert.equal(otherReceipts.get('other_request').ok,true);
    roomClient.publish(`buddycheck/${otherProject}/commands/edge1`,JSON.stringify({command_id:'other_safe',action:'SAFE',actor:'edge1',event_id:otherEvent.event_id,sent_at_ms:Date.now()}),{qos:1});
    await waitFor(() => otherDashboard.locator('#events').innerText().then((text) => text.includes("I'M SAFE")),'second room reply');
    assert.equal(await dashboard.locator('.event-card').count(),1,'second room incident must not leak to primary room');
    console.log('PASS: events, requests, and replies stay in their own group; cross-room requests are rejected.');
    await delay(1100);
    await incident(phoneB);
    await phoneA.getByRole('button',{name:'REQUEST STATUS'}).click();
    await phoneB.locator('#incomingRequest').waitFor({state:'visible'});
    await phoneB.getByRole('button',{name:'NEED HELP',exact:true}).click();
    await phoneA.getByRole('button',{name:'Sudah ditindaklanjuti'}).click();
    await waitFor(() => dashboard.locator('#events').innerText().then((text) => text.includes('Pengecekan selesai')),'need help acknowledgement');
    console.log('PASS: reverse roles, NEED HELP, and buddy acknowledgement.');
    console.log('PASS: incoming request vibration, no repeat on heartbeat, and no-vibration browser fallback.');
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
    const telemetryAddress = `buddycheck/${project}/edge/edge1/telemetry`;
    roomClient.publish(`buddycheck/${project}/receipts/edge1`,JSON.stringify({
      kind:'telemetry',ok:false,code:'SENSOR_SESSION_CONFLICT',
      actor:'edge1',boot_id:'unrelated_session',project_id:project,
    }),{qos:1});
    await delay(300);
    assert.equal(await phoneA.locator('#stopButton').isVisible(),true,'another session receipt cannot stop this phone');
    roomClient.publish(telemetryAddress,JSON.stringify({
      device_id:'edge1',boot_id:'replacement_session',sequence:0,sent_at_ms:Date.now(),
      motion_rms:0.1,rotation_rad:0.01,accel_peak:0.2,window_ms:1000,sample_count:20,source:'simulator',
    }),{qos:1});
    await waitFor(() => phoneA.locator('#notice').innerText().then((text) => text.includes('digantikan sesi lain')),'replaced sender sees conflict');
    assert.equal(await phoneA.locator('#startButton').isVisible(),true);
    assert.equal(await phoneA.locator('#role').isEnabled(),true,'user can correct the phone role');
    assert.equal(await phoneB.locator('#stopButton').isVisible(),true,'other role remains connected');
    await phoneA.getByRole('button',{name:'Mulai sensor & hubungkan'}).click();
    await waitFor(() => dashboard.locator('#edge1-source').innerText().then((text) => text.includes('Sensor fisik')),'sensor recovers after explicit restart');
    console.log('PASS: replaced sensor gets a scoped conflict message, stops publishing, and can reconnect; other role stays connected.');
    for (const page of [dashboard,phoneA,phoneB]) {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth>innerWidth),false,'no horizontal overflow');
    }
    await dashboard.screenshot({path:path.join(root,'test-results/dashboard-flow.png'),fullPage:true});
    await phoneA.screenshot({path:path.join(root,'test-results/phone-flow.png'),fullPage:true});
    child.kill();
    await waitFor(() => dashboard.locator('#detectorStatus').innerText().then((text) => text.includes('offline')),'detector disconnect');
    await waitFor(() => otherDashboard.locator('#detectorStatus').innerText().then((text) => text.includes('offline')),'detector disconnect in other room');
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
    if(roomPulse) clearInterval(roomPulse);
    if(roomClient) roomClient.end(true);
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
