const {test} = require('node:test');
const assert = require('node:assert/strict');
const {features, actions} = require('../web/core.js');

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
