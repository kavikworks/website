const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../guides/lead-response-cost.html'), 'utf8');
const script = html.match(/<script id="intake-cost-script">([\s\S]*?)<\/script>/)[1];

function calculator(values) {
  const nodes = {};
  for (const id of ['intake-cost-form', 'intake-cost-result', 'cost-requests', 'cost-minutes', 'cost-hourly']) {
    nodes[id] = { value: '', textContent: '', hidden: true, handlers: {},
      addEventListener(name, fn) { this.handlers[name] = fn; }, reportValidity() { return true; } };
  }
  ['cost-requests', 'cost-minutes', 'cost-hourly'].forEach((id, i) => { nodes[id].value = values[i]; });
  vm.runInNewContext(script, { document: { getElementById: id => nodes[id] }, Intl, Number });
  let prevented = false;
  nodes['intake-cost-form'].handlers.submit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(nodes['intake-cost-form'].hidden, false);
  return nodes;
}

test('manual intake arithmetic uses minutes-to-hours and USD without inventing savings', () => {
  const nodes = calculator(['120', '5', '30']);
  assert.equal(nodes['intake-cost-result'].hidden, false);
  assert.match(nodes['intake-cost-result'].textContent, /10 hours per month; \$300\.00 USD per month/);
  assert.match(nodes['intake-cost-result'].textContent, /baseline, not promised savings/);
  assert.match(calculator(['10', '1.5', '25'])['intake-cost-result'].textContent, /0.25 hours per month; \$6\.25/);
});

test('real zero is valid but blank, fractional count, negative and nonfinite figures are not', () => {
  assert.match(calculator(['0', '5', '30'])['intake-cost-result'].textContent, /0 hours per month; \$0\.00/);
  for (const values of [['', '5', '30'], ['10', ' ', '30'], ['10', '5', ''],
    ['-1', '5', '30'], ['1.5', '5', '30'], ['10', '-5', '30'], ['10', '5', '-30'],
    ['Infinity', '5', '30'], ['10', 'NaN', '30'], ['10', '5', '1e309'],
    ['1000001', '5', '30'], ['10', '1441', '30'], ['10', '5', '1000001']]) {
    assert.match(calculator(values)['intake-cost-result'].textContent, /Enter all three figures/);
  }
});

test('editing or clearing figures removes the old result', () => {
  const nodes = calculator(['120', '5', '30']);
  for (const event of ['input', 'reset']) {
    nodes['intake-cost-result'].textContent = 'Stale estimate';
    nodes['intake-cost-result'].hidden = false;
    nodes['intake-cost-form'].handlers[event]();
    assert.equal(nodes['intake-cost-result'].hidden, true);
    assert.equal(nodes['intake-cost-result'].textContent, '');
  }
});

test('worksheet is local-only and progressively enhanced with accessible labels', () => {
  for (const prohibited of ['fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage', 'sendBeacon',
    'innerHTML', 'location.', 'mailto:', 'document.cookie']) assert.ok(!script.includes(prohibited));
  assert.match(html, /<form id="intake-cost-form" hidden/);
  assert.match(html, /role="status" aria-live="polite"/);
  for (const id of ['cost-requests', 'cost-minutes', 'cost-hourly']) {
    assert.ok(html.includes('for="' + id + '"'));
    const input = html.match(new RegExp('<input id="' + id + '"[^>]+>'))[0];
    assert.ok(!input.includes('name='));
  }
  assert.match(html, /<noscript>/);
  assert.match(html, /entries are not sent, saved, or added to an email request/);
  assert.match(html, /href="\/sample-workflow\/"/);
  assert.match(html, /"dateModified":"2026-10-16"/);
});
