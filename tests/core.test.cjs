const {test} = require('node:test');
const assert = require('node:assert/strict');
const {features, actions, notificationType} = require('../web/core.js');

test('browser and Python feature units match including a brief acceleration peak', () => {
  const samples = Array.from({length:5}, (_,i) => ({time:i*250,accel:[0,0,9.81+(i===2?4:0)],gyro:[0,0,2]}));
  assert.deepEqual(features(samples),{motion_rms:1.7889,rotation_rad:2,accel_peak:4,window_ms:1000,sample_count:5});
});
test('stationary samples have zero motion, rotation, and peak', () => {
  const samples = Array.from({length:5}, (_,i) => ({time:i*250,accel:[0,0,9.81],gyro:[0,0,0]}));
  assert.equal(features(samples).motion_rms,0);
});
test('invalid/incomplete sensor windows rejected', () => {
  assert.throws(() => features([]));
  assert.throws(() => features(Array(4).fill({time:0,accel:[null,0,0],gyro:[0,0,0]})));
  assert.throws(() => features(Array(4).fill({time:100,accel:[0,0,9.81],gyro:[0,0,0]})));
});
test('only buddy can request, only subject can answer, dashboard cannot impersonate phones', () => {
  const event = {subject:'edge1',buddy:'edge2',status:'CHECK_BUDDY'};
  assert.deepEqual(actions(event,'edge2'),['REQUEST_STATUS']);
  assert.deepEqual(actions(event,'edge1'),[]);
  event.status='AWAITING_REPLY';
  assert.deepEqual(actions(event,'edge1'),['SAFE','NEED_HELP']);
  assert.deepEqual(actions(event,'edge2'),[]);
  assert.deepEqual(actions(event,'dashboard'),[]);
});
test('no response can be retried or marked handled; need help must be handled', () => {
  const event = {subject:'edge2',buddy:'edge1',status:'NO_RESPONSE'};
  assert.deepEqual(actions(event,'edge1'),['REQUEST_STATUS','ACKNOWLEDGE']);
  event.status='NEED_HELP';
  assert.deepEqual(actions(event,'edge1'),['ACKNOWLEDGE']);
});

test('incoming request alerts the subject once, not the sender or dashboard', () => {
  const event={subject:'edge1',buddy:'edge2',status:'AWAITING_REPLY'};
  assert.equal(notificationType(event,'edge1','CHECK_BUDDY'),'request');
  assert.equal(notificationType(event,'edge1','AWAITING_REPLY'),null);
  assert.equal(notificationType(event,'edge2','CHECK_BUDDY'),null);
  assert.equal(notificationType(event,'dashboard','CHECK_BUDDY'),null);
  assert.equal(notificationType(event,'edge1','NO_RESPONSE'),'request');
});
test('completed history is silent on connect but unresolved requests still alert', () => {
  const event={subject:'edge1',buddy:'edge2',status:'SAFE'};
  assert.equal(notificationType(event,'edge2',undefined,true),null);
  assert.equal(notificationType(event,'edge2','AWAITING_REPLY',false),'safe');
  event.status='AWAITING_REPLY';
  assert.equal(notificationType(event,'edge1',undefined,true),'request');
});
test('buddy checks and help notifications go only to the buddy', () => {
  const event={subject:'edge2',buddy:'edge1',status:'CHECK_BUDDY'};
  assert.equal(notificationType(event,'edge1',undefined),'buddy');
  assert.equal(notificationType(event,'edge2',undefined),null);
  event.status='NEED_HELP';
  assert.equal(notificationType(event,'edge1','AWAITING_REPLY'),'urgent');
});
