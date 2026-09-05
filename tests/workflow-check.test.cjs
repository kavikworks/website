const test = require('node:test');
const assert = require('node:assert/strict');
const { makeBrief, readCampaign, tagLink } = require('../workflow-check.js');

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

const campaignQuery = '?utm_source=linkedin&utm_medium=organic_social&utm_campaign=kw-202609-organic-01&utm_content=post-01';

test('a campaign survives the sample-to-intake path and appears in the sent-ready brief', () => {
  const source = readCampaign(campaignQuery);
  const sample = new URL('https://kavikworks.com/sample-workflow/' + campaignQuery);
  const intake = new URL(tagLink('/intake', sample.href, source), sample.href);
  const brief = makeBrief('quotes', 'Gmail', 'Assign an owner', readCampaign(intake.search));
  assert.match(brief.brief, /utm_campaign: kw-202609-organic-01/);
  assert.match(brief.brief, /utm_content: post-01/);
  assert.equal(new URL(brief.mailto).searchParams.get('body'), brief.brief);
  assert.ok(!makeBrief('quotes', 'Gmail', 'Assign an owner', null).brief.includes('utm_'));
});

test('campaign labels reject missing, duplicate, oversized, personal, or injected values', () => {
  for (const query of ['', '?utm_source=linkedin', campaignQuery + '&utm_source=other',
    campaignQuery.replace('post-01', 'post%0ABcc:other@example.com'),
    campaignQuery.replace('post-01', 'person@example.com'),
    campaignQuery.replace('post-01', 'a'.repeat(65)), '?x=' + 'a'.repeat(2048)]) {
    assert.equal(readCampaign(query), null);
  }
  const result = makeBrief('quotes', 'Gmail', 'Assign an owner', { utm_source: 'evil\nBcc: other@example.com' });
  assert.ok(!result.brief.includes('Bcc:'));
  assert.deepEqual(Object.keys(readCampaign(campaignQuery + '&email=private@example.com')), ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']);
});

test('link tagging preserves anchors and destination campaigns without leaking to other origins', () => {
  const campaign = readCampaign(campaignQuery);
  const base = 'https://kavikworks.com/';
  assert.equal(tagLink('https://other.example/intake', base, campaign), 'https://other.example/intake');
  assert.equal(tagLink('mailto:someone@example.com', base, campaign), 'mailto:someone@example.com');
  assert.equal(tagLink('/intake?utm_content=another-post', base, campaign), '/intake?utm_content=another-post');
  const link = new URL(tagLink('/intake?workflow=quotes#main', base, campaign), base);
  assert.equal(link.hash, '#main');
  assert.equal(link.searchParams.get('workflow'), 'quotes');
  assert.equal(link.searchParams.get('utm_content'), 'post-01');
  const email = tagLink('mailto:josh@kavikworks.com?subject=Question', base, campaign);
  assert.equal(new URL(email).searchParams.get('subject'), 'Question');
  assert.match(new URL(email).searchParams.get('body'), /utm_content: post-01/);
  assert.equal(tagLink(email, base, campaign), email);
});

test('the intake source choice removes labels from both copy text and the email draft', () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const nodes = {};
  for (const id of ['workflow-form', 'include-campaign', 'campaign-choice', 'workflow', 'tools', 'handoff',
    'plan-steps', 'email-brief', 'email-request', 'starter-result', 'copy-status', 'result-title', 'copy-brief']) {
    nodes[id] = { value: '', hidden: false, checked: true, handlers: {}, children: [],
      addEventListener(type, fn) { this.handlers[type] = fn; },
      reportValidity() { return true; }, replaceChildren() { this.children = []; },
      appendChild(child) { this.children.push(child); }, focus() {} };
  }
  nodes.workflow.value = 'quotes';
  nodes.tools.value = 'Gmail';
  nodes.handoff.value = 'Assign an owner';
  nodes['starter-result'].hidden = true;
  const context = { URL, URLSearchParams, window: { location: { search: campaignQuery, href: 'https://kavikworks.com/intake' + campaignQuery } },
    document: { getElementById: id => nodes[id], querySelectorAll: () => [], createElement: () => ({}) } };
  vm.runInNewContext(fs.readFileSync(require.resolve('../workflow-check.js'), 'utf8'), context);
  nodes['workflow-form'].handlers.submit({ preventDefault() {} });
  assert.equal(nodes['starter-result'].hidden, false);
  assert.match(nodes['email-brief'].value, /utm_content: post-01/);
  nodes['include-campaign'].checked = false;
  nodes['include-campaign'].handlers.change();
  assert.ok(!nodes['email-brief'].value.includes('utm_'));
  assert.equal(new URL(nodes['email-request'].href).searchParams.get('body'), nodes['email-brief'].value);
});
