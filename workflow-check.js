/* Local-only starter plan and campaign labels. No background submission or storage. */
(function () {
  'use strict';
  const campaignKeys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
  function readCampaign(search) {
    if (String(search).length > 2048) return null;
    const params = new URLSearchParams(search);
    const campaign = {};
    for (const key of campaignKeys) {
      const values = params.getAll(key);
      if (values.length !== 1 || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(values[0])) return null;
      campaign[key] = values[0];
    }
    return campaign;
  }
  function campaignText(value) {
    if (!value || typeof value !== 'object') return '';
    const campaign = readCampaign(new URLSearchParams(campaignKeys.map(key => [key, value[key] || ''])));
    if (!campaign) return '';
    return 'Campaign source (optional; you may remove this):\n' + campaignKeys.map(key => key + ': ' + campaign[key]).join('\n');
  }
  function tagLink(href, base, campaign) {
    const source = campaignText(campaign);
    if (!source) return href;
    let url;
    try { url = new URL(href, base); } catch (_) { return href; }
    if (url.protocol === 'mailto:' && url.pathname === 'josh@kavikworks.com') {
      const body = url.searchParams.get('body') || '';
      if (!body.includes('Campaign source (optional; you may remove this):')) {
        url.searchParams.set('body', (body ? body + '\n\n' : '') + source);
      }
      return url.href;
    }
    if (url.origin !== new URL(base).origin || !/^https?:$/.test(url.protocol)) return href;
    // An explicitly tagged destination owns its attribution. Never create a mixed campaign.
    if (campaignKeys.some(key => url.searchParams.has(key))) return href;
    campaignKeys.forEach(key => url.searchParams.set(key, campaign[key]));
    return url.pathname + url.search + url.hash;
  }
  const plans = {
    quotes: ['Capture contact method, service location, request, and preferred timing in one record.', 'Assign an office or estimating owner. Ask for any missing information before promising a quote.', 'Use a reviewed acknowledgement that explains the next step without confirming price or availability.', 'Track owner, status, and next action. Review unassigned requests during your normal working day.'],
    leasing: ['Capture the property of interest, desired move date, and preferred contact method.', 'Route availability questions to the leasing owner. Keep screening and eligibility decisions with your team.', 'Use an approved reply that explains how to check current availability; do not invent a listing or promise a showing.', 'Track the handoff and outcome. Keep maintenance emergencies on your existing emergency contact route.'],
    inbox: ['Choose a small set of administrative categories and a catch-all review queue.', 'Record the request, original message link, responsible person, and next action.', 'Prepare a short response for each common category and check it before sending.', 'Review unassigned requests and exceptions. Keep sensitive decisions with the responsible person.']
  };
  function makeBrief(kind, currentTools, handoff, campaign = null) {
    if (!Object.prototype.hasOwnProperty.call(plans, kind)) throw new Error('Choose a supported workflow.');
    const toolsText = String(currentTools).trim().slice(0, 150);
    const handoffText = String(handoff).trim().slice(0, 500);
    if (!toolsText || !handoffText) throw new Error('Please complete all three questions.');
    const labels = { quotes: 'Quote or estimate requests', leasing: 'Leasing or availability inquiries', inbox: 'Shared administrative inbox' };
    const brief = [
      'Hi Kavik Works,', '',
      'I am interested in the $149 Workflow Blueprint. Please confirm fit, scope, and delivery timing before payment.', '',
      'Workflow: ' + labels[kind],
      'Current tools: ' + toolsText,
      'Handoff to improve: ' + handoffText, '',
      'Business name / website (optional):', '', 'Thanks',
      ...(campaignText(campaign) ? ['', campaignText(campaign)] : [])
    ].join('\n');
    return { steps: plans[kind].slice(), brief, mailto: 'mailto:josh@kavikworks.com?subject=' + encodeURIComponent('Workflow Blueprint request — ' + labels[kind]) + '&body=' + encodeURIComponent(brief) };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { makeBrief, readCampaign, tagLink };
  if (typeof document === 'undefined') return;
  const campaign = readCampaign(window.location.search);
  if (campaign) {
    document.querySelectorAll('a[href]').forEach(function (link) {
      link.setAttribute('href', tagLink(link.getAttribute('href'), window.location.href, campaign));
    });
  }
  const form = document.getElementById('workflow-form');
  if (!form) return;
  const sourceChoice = document.getElementById('include-campaign');
  document.getElementById('campaign-choice').hidden = !campaign;
  function showPlan() {
    const result = makeBrief(document.getElementById('workflow').value, document.getElementById('tools').value, document.getElementById('handoff').value, sourceChoice.checked ? campaign : null);
    const list = document.getElementById('plan-steps');
    list.replaceChildren();
    result.steps.forEach(function (step) { const item = document.createElement('li'); item.textContent = step; list.appendChild(item); });
    document.getElementById('email-brief').value = result.brief;
    document.getElementById('email-request').href = result.mailto;
    document.getElementById('starter-result').hidden = false;
    document.getElementById('copy-status').textContent = '';
    document.getElementById('result-title').focus();
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (form.reportValidity()) showPlan();
  });
  sourceChoice.addEventListener('change', function () {
    if (!document.getElementById('starter-result').hidden && form.reportValidity()) showPlan();
  });
  document.getElementById('copy-brief').addEventListener('click', async function () {
    const field = document.getElementById('email-brief');
    const status = document.getElementById('copy-status');
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(field.value);
      status.textContent = 'Brief copied. Paste it into your email app and send when ready.';
    } catch (_) {
      field.focus(); field.select();
      status.textContent = 'Your brief is selected. Use your device’s Copy command, then paste it into your email app.';
    }
  });
}());
