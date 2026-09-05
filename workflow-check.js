/* Local-only starter plan. No background submission, analytics, or storage. */
(function () {
  'use strict';
  const plans = {
    quotes: ['Capture contact method, service location, request, and preferred timing in one record.', 'Assign an office or estimating owner. Ask for any missing information before promising a quote.', 'Use a reviewed acknowledgement that explains the next step without confirming price or availability.', 'Track owner, status, and next action. Review unassigned requests during your normal working day.'],
    leasing: ['Capture the property of interest, desired move date, and preferred contact method.', 'Route availability questions to the leasing owner. Keep screening and eligibility decisions with your team.', 'Use an approved reply that explains how to check current availability; do not invent a listing or promise a showing.', 'Track the handoff and outcome. Keep maintenance emergencies on your existing emergency contact route.'],
    inbox: ['Choose a small set of administrative categories and a catch-all review queue.', 'Record the request, original message link, responsible person, and next action.', 'Prepare a short response for each common category and check it before sending.', 'Review unassigned requests and exceptions. Keep sensitive decisions with the responsible person.']
  };
  function makeBrief(kind, currentTools, handoff) {
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
      'Business name / website (optional):', '', 'Thanks'
    ].join('\n');
    return { steps: plans[kind].slice(), brief, mailto: 'mailto:josh@kavikworks.com?subject=' + encodeURIComponent('Workflow Blueprint request — ' + labels[kind]) + '&body=' + encodeURIComponent(brief) };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { makeBrief };
  if (typeof document === 'undefined') return;
  const form = document.getElementById('workflow-form');
  if (!form) return;
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const result = makeBrief(document.getElementById('workflow').value, document.getElementById('tools').value, document.getElementById('handoff').value);
    const list = document.getElementById('plan-steps');
    list.replaceChildren();
    result.steps.forEach(function (step) { const item = document.createElement('li'); item.textContent = step; list.appendChild(item); });
    document.getElementById('email-brief').value = result.brief;
    document.getElementById('email-request').href = result.mailto;
    document.getElementById('starter-result').hidden = false;
    document.getElementById('copy-status').textContent = '';
    document.getElementById('result-title').focus();
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
