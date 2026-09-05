const test = require('node:test');
const assert = require('node:assert/strict');
const { makeBrief } = require('../workflow-check.js');

test('all supported workflows produce a usable request to the verified business inbox', () => {
  for (const kind of ['quotes', 'leasing', 'inbox']) {
    const plan = makeBrief(kind, 'Gmail & Sheets', 'Give each request an owner.');
    const url = new URL(plan.mailto);
    assert.equal(url.protocol, 'mailto:');
    assert.equal(url.pathname, 'josh@kavikworks.com');
    assert.equal(url.searchParams.get('body'), plan.brief);
    assert.equal(plan.steps.length, 4);
    assert.match(plan.brief, /confirm fit, scope, and delivery timing before payment/);
    assert.match(plan.brief, /Gmail & Sheets/);
  }
});

test('special characters remain body content and cannot add recipients or headers', () => {
  const value = 'A&B?cc=other@example.com\nBcc: other@example.com <script>é</script>';
  const result = makeBrief('inbox', value, value);
  const url = new URL(result.mailto);
  assert.deepEqual([...url.searchParams.keys()], ['subject', 'body']);
  assert.ok(url.searchParams.get('body').includes(value));
  assert.ok(!result.mailto.includes('\n'));
});

test('invalid or empty workflow input never creates a request', () => {
  for (const kind of ['', 'medical', '__proto__', 'constructor']) {
    assert.throws(() => makeBrief(kind, 'Email', 'Assign work'));
  }
  assert.throws(() => makeBrief('quotes', ' ', 'Assign work'));
  assert.throws(() => makeBrief('quotes', 'Email', ' '));
});

test('long input is bounded and regenerating a plan does not mutate templates', () => {
  const first = makeBrief('quotes', 'x'.repeat(1000), 'y'.repeat(1000));
  assert.ok(!first.brief.includes('x'.repeat(151)));
  assert.ok(!first.brief.includes('y'.repeat(501)));
  first.steps[0] = 'changed';
  assert.notEqual(makeBrief('quotes', 'Email', 'Assign work').steps[0], 'changed');
});
