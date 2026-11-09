import assert from 'node:assert/strict';
import test from 'node:test';
import {watchConnection} from '../connection.js';

test('connection retries automatically and stops timers when the panel closes', async () => {
  const reports = [], timers = [];
  let online = false, calls = 0, cancelled;
  const stop = watchConnection({}, state => reports.push(state), {
    sync: async () => { calls++; return online; },
    schedule: callback => { timers.push(callback); return timers.length; },
    cancel: timer => { cancelled = timer; },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(reports, [false]);
  assert.equal(calls, 1);
  online = true;
  await timers[0]();
  assert.deepEqual(reports, [false, true]);
  assert.equal(calls, 2);
  stop();
  assert.equal(cancelled, 2);
  await timers[1]();
  assert.equal(calls, 2);
});

test('a panel closed during native discovery never schedules more work', async () => {
  let finish;
  const stop = watchConnection({}, () => assert.fail('closed panel'), {
    sync: () => new Promise(resolve => { finish = resolve; }),
    schedule: () => assert.fail('closed panel'), cancel: () => {},
  });
  stop();
  finish(true);
  await new Promise(resolve => setImmediate(resolve));
});
