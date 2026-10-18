'use strict';

(() => {
  const byId = (id) => document.getElementById(id);
  const API_PATHS = new Set([
    '/api/current', '/api/brief', '/api/checkout', '/api/pay', '/api/reconcile',
    '/api/retry', '/api/report', '/api/revision', '/api/recovery', '/api/recover',
    '/api/operator/login', '/api/operator/orders', '/api/operator/action',
  ]);
  const ROUTES = new Set(['/', '/checkout', '/order', '/operator']);
  const WORKFLOWS = {
    QUOTE_REQUEST: 'Quote-request follow-up',
    LEASING_INQUIRY: 'Leasing-inquiry handoff',
    ADMIN_INBOX: 'Shared administrative inbox',
    OTHER: 'Other workflow — scope review needed',
  };
  const RETRY_STATES = new Set(['EXPIRED', 'PAYMENT_FAILED', 'CAPACITY_UNAVAILABLE', 'PAYMENT_UNAVAILABLE']);
  const PAID_CASE_STATES = new Set([
    'DRAFTING', 'READY_FOR_QA', 'QA_CHANGES', 'QA_PASS', 'DELIVERED',
    'REVISION_REQUESTED', 'REVISION_READY_FOR_QA', 'REVISION_QA_PASS', 'REVISION_DELIVERED',
  ]);
  const state = {
    current: null,
    busy: false,
    phase: 'welcome',
    connected: false,
    submission: null,
    needsReconcile: false,
    report: null,
    reportOrder: null,
    recoveryKey: null,
    briefLockedOrders: new Set(),
    operatorAuthenticated: false,
    operatorOrders: [],
  };

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function show(id, visible) {
    byId(id).hidden = !visible;
  }

  function text(id, value) {
    byId(id).textContent = value === undefined || value === null ? '' : String(value);
  }

  function announce(message) {
    text('notice', message);
  }

  function focusHeading(id) {
    requestAnimationFrame(() => {
      const target = byId(id);
      if (!target || target.hidden || target.closest('[hidden]')) return;
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'start', behavior: 'instant' });
    });
  }

  function clearError() {
    show('error-banner', false);
    text('error-message', '');
  }

  function displayError(error) {
    text('error-message', error.message || 'The local preview could not complete that action. Refresh the status before trying again.');
    show('error-banner', true);
    byId('error-banner').focus();
  }

  class PreviewError extends Error {
    constructor(message, code = 'PREVIEW_ERROR', fields = null, status = null) {
      super(message);
      this.name = 'PreviewError';
      this.code = code;
      this.fields = fields;
      this.status = status;
    }
  }

  async function request(path, body) {
    if (!API_PATHS.has(path)) throw new PreviewError('This action is not part of the local preview.');
    const isPost = body !== undefined;
    const headers = { Accept: 'application/json' };
    if (isPost) {
      if (!state.current || typeof state.current.csrf !== 'string' || !state.current.csrf) {
        throw new PreviewError('Refresh the preview to restore its local session before continuing.');
      }
      headers['Content-Type'] = 'application/json';
      headers['X-Preview-CSRF'] = state.current.csrf;
    }
    let response;
    try {
      response = await fetch(path, {
        method: isPost ? 'POST' : 'GET',
        credentials: 'same-origin',
        mode: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        headers,
        ...(isPost ? { body: JSON.stringify(body) } : {}),
      });
    } catch (_) {
      if (isPost) state.needsReconcile = true;
      throw new PreviewError(isPost
        ? 'The response could not be confirmed. Refresh the preview order status before trying another action.'
        : 'The local preview server could not be reached. Check that it is running, then try again.', 'CONNECTION_ERROR');
    }
    let data;
    try {
      data = await response.json();
    } catch (_) {
      if (isPost) state.needsReconcile = true;
      throw new PreviewError('The preview returned an unreadable response. Refresh the status before continuing.', 'INVALID_RESPONSE');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      if (isPost) state.needsReconcile = true;
      throw new PreviewError('The preview returned an unreadable response. Refresh the status before continuing.', 'INVALID_RESPONSE');
    }
    if (!response.ok || data.error) {
      throw new PreviewError(typeof data.message === 'string' ? data.message : 'This preview action is not available in the current state.',
        typeof data.error === 'string' ? data.error : 'PREVIEW_ERROR', data.fields, response.status);
    }
    return data;
  }

  function acceptCurrent(data) {
    if (!data || data.mode !== 'LOCAL_FAKE_PREVIEW' || data.sample_only !== true ||
        typeof data.csrf !== 'string' || !data.csrf || !Object.hasOwn(data, 'order')) {
      throw new PreviewError('The server did not identify itself as the local fake preview. Actions are blocked.', 'MODE_MISMATCH');
    }
    const previousOrder = state.current && state.current.order;
    const previousId = previousOrder && previousOrder.id;
    const newlyDeliveredRevision = data.order && data.order.case && data.order.case.state === 'REVISION_DELIVERED' &&
      (!previousOrder || !previousOrder.case || previousOrder.case.state !== 'REVISION_DELIVERED');
    state.current = data;
    state.connected = true;
    if (data.order && ['CHECKOUT_OPEN', 'PAYMENT_PENDING', 'PAYMENT_FAILED', 'PAYMENT_REVIEW', 'PAID'].includes(data.order.state)) {
      state.briefLockedOrders.add(data.order.id);
    }
    if (!data.order || previousId !== data.order.id) {
      state.report = null;
      state.reportOrder = null;
      state.recoveryKey = null;
    }
    if (newlyDeliveredRevision) {
      state.report = null;
      state.reportOrder = null;
    }
  }

  async function refreshCurrent() {
    acceptCurrent(await request('/api/current'));
    state.needsReconcile = false;
  }

  async function runAction(work, successMessage) {
    if (state.busy) return;
    clearError();
    announce('');
    state.busy = true;
    byId('main').setAttribute('aria-busy', 'true');
    const controls = [...document.querySelectorAll('button, input, textarea, select')].map((control) => [control, control.disabled]);
    controls.forEach(([control]) => { control.disabled = true; });
    try {
      await work();
      if (successMessage) announce(successMessage);
    } catch (error) {
      if (error.code === 'BRIEF_LOCKED') {
        if (state.current && state.current.order) state.briefLockedOrders.add(state.current.order.id);
        try { await refreshCurrent(); } catch (_) { /* Keep the original safe scope-lock error. */ }
        state.phase = 'summary';
        navigate('/');
      }
      applyServerFields(error.fields);
      displayError(error);
    } finally {
      state.busy = false;
      byId('main').removeAttribute('aria-busy');
      controls.forEach(([control, disabled]) => { if (control.isConnected) control.disabled = disabled; });
      render();
    }
  }

  function route() {
    return ROUTES.has(window.location.pathname) ? window.location.pathname : '/';
  }

  function navigate(path, heading) {
    if (!ROUTES.has(path)) return;
    // Route paths contain no brief, recovery key, token, or other form data.
    if (window.location.pathname !== path) window.history.pushState(null, '', path);
    clearError();
    render();
    if (heading) focusHeading(heading);
    else window.scrollTo({ top: 0, behavior: 'instant' });
  }

  function dateValue(value, endOfDay = false) {
    if (typeof value !== 'string' || !value) return null;
    const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? `${value}T${endOfDay ? '23:59:59' : '12:00:00'}Z` : value;
    const date = new Date(normalized);
    return Number.isFinite(date.getTime()) ? date : null;
  }

  function formatDate(value) {
    const date = dateValue(value);
    return date ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(date) : 'Not available yet';
  }

  function formatDateTime(value) {
    const date = dateValue(value);
    return date ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' }).format(date) : 'Not available';
  }

  function money(cents) {
    return Number.isSafeInteger(cents) && cents >= 0
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100)
      : 'Unavailable';
  }

  function workflowLabel(value) {
    return WORKFLOWS[value] || 'Workflow awaiting scope review';
  }

  function readable(value) {
    if (typeof value !== 'string' || !value) return 'Not available';
    return value.toLowerCase().replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase());
  }

  function paid(order) {
    return order.state === 'PAID' && order.case && PAID_CASE_STATES.has(order.case.state);
  }

  function canOpenCheckout(order) {
    return order.state === 'RESERVED' && order.scope_status === 'ELIGIBLE' &&
      order.reservation_state === 'HELD' && Boolean(dateValue(order.delivery_date)) &&
      order.price && order.price.currency === 'USD' && order.price.total_cents === 14900 &&
      !state.needsReconcile;
  }

  function canPay(order) {
    return order.state === 'CHECKOUT_OPEN' && order.scope_status === 'ELIGIBLE' &&
      order.reservation_state === 'HELD' && !state.needsReconcile;
  }

  function statusDescription(order) {
    const definitions = {
      RESERVED: ['Sample capacity reserved', 'Your fictional brief fits the written-plan scope. Review the sample date and price before opening fake checkout.', 'teal'],
      CHECKOUT_OPEN: ['Your fake checkout is ready', 'A fictional capacity hold is in place. You can simulate a payment outcome; no card or live payment is involved.', 'teal'],
      PAYMENT_PENDING: ['The sample payment is still processing', 'Payment has not been confirmed. The fictional capacity hold remains in place while the server reconciles the outcome. Do not create a second payment.', 'amber'],
      PAYMENT_FAILED: ['The sample payment did not complete', 'No paid order has been confirmed. Check availability again to obtain a fresh fictional reservation before retrying.', 'amber'],
      CANCELLED: ['The fake checkout was left', 'No payment was confirmed by this preview. The local server controls whether the fictional reservation has been released.', 'amber'],
      EXPIRED: ['The sample reservation has expired', 'The previous checkout is no longer current. Check availability again for a fresh, feasible fictional reservation.', 'amber'],
      CAPACITY_UNAVAILABLE: ['No fictional delivery slot is available', 'The preview cannot reserve an achievable sample date right now. Check availability again without creating another order.', 'amber'],
      PAYMENT_UNAVAILABLE: ['Fake checkout is unavailable', 'The preview has not confirmed payment. Check availability again when the local fake provider is ready.', 'amber'],
      NEEDS_REVIEW: ['This workflow needs a scope review', 'The brief is saved, but the preview cannot open checkout or promise a delivery date. Keep the request to one administrative workflow and review the scope details.', 'amber'],
      UNSUPPORTED: ['This request is outside the written-plan scope', 'Checkout is blocked. The Workflow Blueprint covers one administrative workflow and excludes regulated decisions, emergency dispatch, installation, and account access.', 'red'],
      PAID: ['Sample payment recorded', 'The local fake provider has recorded a fictional payment. Follow the sample drafting, simulated QA, and private delivery status here.', 'teal'],
      PAYMENT_REVIEW: ['The sample payment needs reconciliation', 'The recorded outcome needs review before fulfillment can proceed. No delivery is confirmed. Keep this order and refresh its status rather than submitting another payment.', 'amber'],
    };
    return definitions[order.state] || ['Status needs review', 'The local server returned a state this interface does not recognize. Refresh the status before taking another action.', 'amber'];
  }

  function caseDescription(caseRecord) {
    const definitions = {
      DRAFTING: ['Your sample Blueprint is being drafted', 'The fictional brief is ready for sample drafting. The written plan will remain private until the simulated review and delivery steps are complete.'],
      READY_FOR_QA: ['The sample is ready for simulated QA', 'Drafting is complete in the preview. Simulated independent agent QA comes before delivery; there is nothing for you to approve here.'],
      QA_CHANGES: ['The sample needs a few corrections', 'Simulated QA requested changes. The sample remains private while those corrections are prepared and reviewed.'],
      QA_PASS: ['Simulated QA is complete', 'The sample has passed the operator’s simulated QA step. Private delivery has not been confirmed yet.'],
      DELIVERED: ['Your sample Workflow Blueprint is ready', 'The local server has confirmed fictional delivery. Open the private sample below, or download a copy.'],
      REVISION_REQUESTED: ['Your clarification request is saved', 'The included sample clarification is queued for drafting and simulated QA. Your previously delivered sample remains available.'],
      REVISION_READY_FOR_QA: ['The sample clarification is in simulated QA', 'The updated draft is awaiting the simulated independent review step. The previous delivered version remains available until revision delivery.'],
      REVISION_QA_PASS: ['The sample clarification passed simulated QA', 'The updated sample is ready for private revision delivery. The previous delivered version remains available until that is confirmed.'],
      REVISION_DELIVERED: ['Your sample clarification is ready', 'The local server has confirmed fictional revision delivery. Open the updated private sample below. Your included clarification revision is complete.'],
    };
    return definitions[caseRecord.state] || ['Fulfillment status needs review', 'Refresh the local preview status before assuming the sample has been delivered.'];
  }

  function appendReasons(container, reasons) {
    container.replaceChildren();
    if (!Array.isArray(reasons)) return;
    for (const reason of reasons) {
      if (typeof reason === 'string' && reason) container.append(node('li', '', readable(reason)));
    }
  }

  function fillBrief(brief) {
    if (!brief) return;
    byId('workflow').value = Object.hasOwn(WORKFLOWS, brief.workflow) ? brief.workflow : '';
    byId('tools').value = typeof brief.tools === 'string' ? brief.tools : '';
    byId('handoff').value = typeof brief.handoff === 'string' ? brief.handoff : '';
    for (const [key, id] of [['admin_only', 'admin-only'], ['one_workflow', 'one-workflow'], ['no_sensitive_data', 'no-sensitive-data'], ['written_plan_only', 'written-plan-only']]) {
      byId(id).checked = brief[key] === true;
    }
    updateCount();
  }

  function clearFieldErrors() {
    document.querySelectorAll('.field-error').forEach((element) => { element.hidden = true; element.textContent = ''; });
    document.querySelectorAll('[aria-invalid]').forEach((element) => element.removeAttribute('aria-invalid'));
  }

  function fieldError(id, errorId, message) {
    byId(id).setAttribute('aria-invalid', 'true');
    text(errorId, message);
    show(errorId, true);
  }

  function applyServerFields(fields) {
    if (!fields || typeof fields !== 'object') return;
    const known = {
      workflow: ['workflow', 'workflow-error'], tools: ['tools', 'tools-error'],
      handoff: ['handoff', 'handoff-error'], admin_only: ['admin-only', 'admin-only-error'],
      one_workflow: ['one-workflow', 'one-workflow-error'], no_sensitive_data: ['no-sensitive-data', 'no-sensitive-data-error'],
      written_plan_only: ['written-plan-only', 'written-plan-only-error'],
      request: ['revision-request', 'revision-error'], recovery_key: ['recover-key', 'recover-error'],
      token: ['operator-token', 'operator-token-error'], accept_preview_terms: ['accept-terms', 'terms-error'],
    };
    for (const [name, message] of Object.entries(fields)) {
      if (Object.hasOwn(known, name) && typeof message === 'string') fieldError(...known[name], message);
    }
  }

  function updateCount() {
    text('handoff-count', `${byId('handoff').value.length} / 600`);
  }

  function startBrief(example = false, editing = false) {
    clearError();
    clearFieldErrors();
    state.phase = 'brief';
    state.submission = null;
    if (editing && state.current.order) fillBrief(state.current.order.brief);
    if (example) {
      fillBrief({
        workflow: 'QUOTE_REQUEST',
        tools: 'TEST_ONLY: shared inbox and a spreadsheet at office.example',
        handoff: 'TEST_ONLY: A fictional quote request arrives in our shared inbox. The office should capture the request in one spreadsheet, assign one follow-up owner, and record the next step. No customer information is included.',
        admin_only: true, one_workflow: true, no_sensitive_data: true, written_plan_only: true,
      });
      announce('A fictional example is filled in. Review the brief and scope confirmations before continuing.');
    }
    navigate('/', 'brief-heading');
  }

  function renderProgress(order) {
    const visible = Boolean(order) || state.phase === 'brief';
    show('progress', visible);
    let active = order ? 1 : 0;
    if (state.phase === 'brief' && route() === '/') active = 0;
    else if (order && (route() === '/checkout' || ['CHECKOUT_OPEN', 'PAYMENT_PENDING', 'PAYMENT_FAILED', 'PAYMENT_REVIEW'].includes(order.state))) active = 2;
    if (order && order.state === 'PAID') active = 3;
    byId('progress').querySelectorAll('li').forEach((item, index) => {
      item.classList.toggle('is-current', index === active);
      item.classList.toggle('is-complete', index < active);
      if (index === active) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
      const number = item.querySelector('.step-index');
      number.textContent = index < active ? '✓' : String(index + 1);
      number.setAttribute('aria-hidden', 'true');
    });
  }

  function renderSummary(order) {
    const [title, description, tone] = statusDescription(order);
    const status = byId('summary-status');
    status.className = `state-message ${tone === 'red' ? 'blocked' : tone === 'amber' ? 'warning' : ''}`;
    status.replaceChildren(node('strong', '', title), node('p', '', description));
    if (Array.isArray(order.scope_reasons) && order.scope_reasons.length) {
      const reasons = node('ul');
      appendReasons(reasons, order.scope_reasons);
      status.append(reasons);
    }
    text('summary-workflow', workflowLabel(order.brief && order.brief.workflow));
    text('summary-tools', order.brief && order.brief.tools);
    text('summary-handoff', order.brief && order.brief.handoff);
    show('scope-confirmation', order.scope_status === 'ELIGIBLE');
    text('summary-date', order.delivery_date ? formatDate(order.delivery_date) : 'Not reserved');
    text('reservation-note', order.reservation_state === 'HELD'
      ? `Fictional capacity held${order.checkout_expires_at ? ` until ${formatDateTime(order.checkout_expires_at)}` : ' by the local preview'}.`
      : 'No active fictional capacity hold.');
    text('summary-subtotal', money(order.price && order.price.subtotal_cents));
    text('summary-tax', money(order.price && order.price.tax_cents));
    text('summary-total', money(order.price && order.price.total_cents));
    show('checkout-start', canOpenCheckout(order));
    show('resume-checkout', order.state === 'CHECKOUT_OPEN' && !state.needsReconcile);
    show('summary-order-link', !canOpenCheckout(order));
    byId('open-checkout').disabled = !canOpenCheckout(order);
    show('edit-brief', ['RESERVED', 'NEEDS_REVIEW', 'UNSUPPORTED', 'CAPACITY_UNAVAILABLE', 'PAYMENT_UNAVAILABLE'].includes(order.state) && !state.briefLockedOrders.has(order.id));
  }

  function renderCheckout(order) {
    text('checkout-workflow', workflowLabel(order.brief && order.brief.workflow));
    text('checkout-subtotal', money(order.price && order.price.subtotal_cents));
    text('checkout-tax', money(order.price && order.price.tax_cents));
    text('checkout-total', money(order.price && order.price.total_cents));
    text('checkout-date', order.delivery_date ? formatDate(order.delivery_date) : 'Not reserved');
    text('checkout-reservation', order.reservation_state === 'HELD' ? 'Fictional hold active' : 'No active hold');
    text('checkout-message', canPay(order)
      ? 'This changes only the local fake provider’s recorded outcome. No card or financial account is connected.'
      : state.needsReconcile ? 'The last response is unconfirmed. Check the order status before another action.'
        : `${statusDescription(order)[0]}. Return to the order status for the next available step.`);
    document.querySelectorAll('[data-outcome]').forEach((button) => { button.disabled = !canPay(order); });
  }

  function actionButton(label, callback, secondary = false) {
    const button = node('button', secondary ? 'button secondary' : 'button', label);
    button.type = 'button';
    button.addEventListener('click', callback);
    return button;
  }

  function routeLink(label, path, secondary = false) {
    const link = node('a', secondary ? 'button secondary' : 'button', label);
    link.href = path;
    link.setAttribute('data-route', '');
    return link;
  }

  function renderTimeline(order) {
    const timeline = byId('order-timeline');
    timeline.replaceChildren();
    if (order.state !== 'PAID' || !order.case) return;
    const stage = order.case.state;
    const revision = stage.startsWith('REVISION_');
    const delivered = stage === 'DELIVERED' || revision;
    const qaPassed = ['QA_PASS', 'DELIVERED'].includes(stage) || revision;
    const qaReady = ['READY_FOR_QA', 'QA_CHANGES'].includes(stage);
    const steps = [
      ['Brief saved', 'One administrative workflow.', true, false],
      ['Fictional payment recorded', 'Confirmed by the local fake provider.', true, false],
      ['Sample drafting', stage === 'QA_CHANGES' ? 'Sample corrections are being prepared.' : 'A written plan from the fictional brief.', qaReady || qaPassed, stage === 'DRAFTING' || stage === 'QA_CHANGES'],
      ['Simulated independent QA', 'A separate operator step in this demonstration.', qaPassed, qaReady && stage !== 'QA_CHANGES'],
      ['Private sample delivery', delivered ? 'The delivered sample is available below.' : 'Available after recorded sample delivery.', delivered, stage === 'QA_PASS'],
    ];
    for (const [label, description, done, current] of steps) {
      const item = node('li', done ? 'done' : current ? 'current' : '');
      const dot = node('span', 'timeline-dot', done ? '✓' : current ? '•' : '');
      dot.setAttribute('aria-hidden', 'true');
      const words = node('div');
      words.append(node('strong', '', label), node('p', '', description));
      if (current) item.setAttribute('aria-current', 'step');
      item.append(dot, words);
      timeline.append(item);
    }
  }

  function revisionAvailable(order) {
    if (!order.case || order.case.state !== 'DELIVERED' || !order.case.report_available) return false;
    const deadline = dateValue(order.case.revision_deadline, true);
    const now = dateValue(state.current.server_time);
    return Boolean(deadline && now && deadline >= now);
  }

  function renderOrder(order) {
    let [title, description, tone] = statusDescription(order);
    if (paid(order)) [title, description] = caseDescription(order.case);
    text('order-reference', `Preview order ${order.id}`);
    text('order-state-label', order.case && order.state === 'PAID' ? readable(order.case.state) : readable(order.state));
    byId('order-state-label').className = `small-tag ${tone}`;
    text('order-state-title', title);
    text('order-state-description', description);
    const reasons = Array.isArray(order.scope_reasons) ? order.scope_reasons : [];
    appendReasons(byId('order-reasons'), reasons);
    show('order-reasons', reasons.length > 0);
    const actions = byId('order-actions');
    actions.replaceChildren();
    if (state.needsReconcile || ['PAYMENT_PENDING', 'PAYMENT_REVIEW'].includes(order.state)) {
      actions.append(actionButton('Check recorded payment status', () => reconcileCurrent()));
    } else if (order.state === 'CHECKOUT_OPEN') {
      actions.append(routeLink('Continue fake checkout →', '/checkout'));
    } else if (RETRY_STATES.has(order.state)) {
      actions.append(actionButton(order.state === 'PAYMENT_FAILED' ? 'Try a fresh checkout →' : 'Check availability again →', () => retryCurrent()));
    } else if (order.state === 'RESERVED') {
      actions.append(routeLink('Review scope & sample date →', '/'));
    } else if (['NEEDS_REVIEW', 'UNSUPPORTED'].includes(order.state) && !state.briefLockedOrders.has(order.id)) {
      actions.append(actionButton('Review the brief', () => startBrief(false, true), true));
    }
    renderTimeline(order);
    text('order-workflow', workflowLabel(order.brief && order.brief.workflow));
    text('order-delivery', order.delivery_date ? `${formatDate(order.delivery_date)} · fictional` : 'Not reserved');
    text('order-total', money(order.price && order.price.total_cents));
    text('order-payment', `${readable(order.payment_status)} · simulated`);
    const hasReport = order.state === 'PAID' && order.case && order.case.report_available === true;
    show('report-section', hasReport);
    show('report-text', hasReport && state.report !== null && state.reportOrder === order.id);
    text('report-text', hasReport && state.reportOrder === order.id ? state.report : '');
    text('view-report', state.report !== null && state.reportOrder === order.id ? 'Refresh private sample' : 'Open private sample');
    const hasRevision = hasReport && (order.case.state === 'DELIVERED' || order.case.state.startsWith('REVISION_'));
    show('revision-section', hasRevision);
    if (hasRevision) {
      const available = revisionAvailable(order);
      show('revision-form', available);
      if (order.case.state === 'REVISION_DELIVERED') text('revision-status', 'Your one included sample clarification has been delivered. The updated sample is available above.');
      else if (order.case.state.startsWith('REVISION_')) text('revision-status', 'Your clarification request is recorded. Follow the sample status above; the previously delivered version remains available until revision delivery.');
      else if (available) text('revision-status', `Request one in-scope clarification by ${formatDate(order.case.revision_deadline)} (sample deadline), within seven days of sample delivery.`);
      else text('revision-status', order.case.revision_deadline ? `The sample clarification window ended on ${formatDate(order.case.revision_deadline)}.` : 'The local server has not provided a sample revision deadline. A revision cannot be requested yet.');
    }
  }

  function renderRecovery(order) {
    show('create-recovery', Boolean(order));
    show('recovery-unavailable', !order);
    show('recovery-key-panel', Boolean(order && state.recoveryKey));
    byId('recovery-key').value = order && state.recoveryKey ? state.recoveryKey : '';
  }

  function operatorActionDefinitions(order) {
    const actions = [];
    const caseState = order.case && order.case.state;
    if (order.state === 'PAYMENT_PENDING') actions.push(['settle_payment', 'Simulate final payment settlement']);
    if (order.state === 'PAID' && (!caseState || ['DRAFTING', 'QA_CHANGES'].includes(caseState))) actions.push(['draft', 'Simulate draft preparation']);
    if (caseState === 'READY_FOR_QA') actions.push(['qa_pass', 'Simulate independent QA pass'], ['qa_fail', 'Simulate QA corrections']);
    if (caseState === 'QA_PASS') actions.push(['deliver', 'Simulate private delivery']);
    if (caseState === 'REVISION_REQUESTED') actions.push(['revision_draft', 'Simulate clarification draft']);
    if (caseState === 'REVISION_READY_FOR_QA') actions.push(['revision_qa_pass', 'Simulate revision QA pass']);
    if (caseState === 'REVISION_QA_PASS') actions.push(['revision_deliver', 'Simulate revision delivery']);
    actions.push(['reconcile', 'Reconcile recorded state']);
    return actions;
  }

  function renderOperator() {
    show('operator-login', !state.operatorAuthenticated);
    show('operator-content', state.operatorAuthenticated);
    const container = byId('operator-orders');
    container.replaceChildren();
    text('operator-count', `${state.operatorOrders.length} fictional ${state.operatorOrders.length === 1 ? 'order' : 'orders'} on this local server`);
    if (!state.operatorOrders.length) {
      const empty = node('div', 'panel');
      empty.append(node('h3', '', 'No sample orders yet.'), node('p', 'muted', 'Start with a fictional customer brief, then return here to walk through simulated fulfillment.'), routeLink('Open customer preview →', '/', true));
      container.append(empty);
    }
    for (const order of state.operatorOrders) {
      const card = node('article', 'panel operator-order');
      const header = node('div', 'operator-order-header');
      const heading = node('div');
      heading.append(node('p', 'eyebrow', 'WORKFLOW BLUEPRINT · FICTIONAL ORDER'), node('h3', '', workflowLabel(order.brief && order.brief.workflow)), node('p', 'mono', order.id));
      header.append(heading, node('span', 'small-tag', order.case ? readable(order.case.state) : readable(order.state)));
      const metadata = node('div', 'operator-metadata');
      metadata.append(node('span', '', `Order: ${readable(order.state)}`), node('span', '', `Payment: ${readable(order.payment_status)}`), node('span', '', `Sample delivery: ${order.delivery_date ? formatDate(order.delivery_date) : 'not reserved'}`));
      const details = node('details');
      details.append(node('summary', '', 'View fictional brief'));
      const summary = node('dl', 'brief-summary');
      for (const [label, value] of [['Tools', order.brief && order.brief.tools], ['Handoff', order.brief && order.brief.handoff], ['Sample QA state', order.case && order.case.qa_state]]) {
        const group = node('div');
        group.append(node('dt', '', label), node('dd', 'preserve-lines', value || 'Not available'));
        summary.append(group);
      }
      details.append(summary);
      const actionRow = node('div', 'button-row');
      for (const [action, label] of operatorActionDefinitions(order)) {
        actionRow.append(actionButton(label, () => performOperatorAction(order.id, action), action !== 'deliver' && action !== 'revision_deliver'));
      }
      card.append(header, metadata, details, actionRow);
      container.append(card);
    }
  }

  function render() {
    const connected = state.connected && state.current;
    show('loading-view', false);
    show('connection-view', !connected);
    show('customer-view', Boolean(connected && route() !== '/operator'));
    show('operator-view', Boolean(connected && route() === '/operator'));
    if (!connected) return;
    if (route() === '/operator') {
      document.title = 'Simulated operator workspace · Private preview · Kavik Works';
      renderOperator();
      return;
    }
    const order = state.current.order;
    for (const id of ['welcome-view', 'brief-view', 'summary-view', 'checkout-view', 'order-view', 'empty-order-view']) show(id, false);
    show('recovery-section', true);
    show('preview-terms', true);
    renderProgress(order);
    renderRecovery(order);
    if (!order) {
      if (route() !== '/') {
        show('empty-order-view', true);
        document.title = 'No preview order · Workflow Blueprint · Kavik Works';
      } else {
        show(state.phase === 'brief' ? 'brief-view' : 'welcome-view', true);
        document.title = 'Workflow Blueprint · Private preview · Kavik Works';
      }
      return;
    }
    if (route() === '/checkout') {
      show('checkout-view', true);
      renderCheckout(order);
      document.title = 'Local fake checkout · Workflow Blueprint · Kavik Works';
    } else if (route() === '/order') {
      show('order-view', true);
      renderOrder(order);
      document.title = 'Your preview order · Workflow Blueprint · Kavik Works';
    } else if (state.phase === 'brief') {
      show('brief-view', true);
      document.title = 'Your fictional brief · Workflow Blueprint · Kavik Works';
    } else {
      show('summary-view', true);
      renderSummary(order);
      document.title = 'Scope & sample date · Workflow Blueprint · Kavik Works';
    }
  }

  async function loadOperatorOrders(silent = false) {
    try {
      const response = await request('/api/operator/orders');
      if (!Array.isArray(response.orders)) throw new PreviewError('The operator response did not include a sample order list.');
      state.operatorOrders = response.orders;
      state.operatorAuthenticated = true;
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        state.operatorAuthenticated = false;
        state.operatorOrders = [];
        if (silent) return;
      }
      throw error;
    }
  }

  async function boot() {
    await runAction(async () => {
      await refreshCurrent();
      state.phase = state.current.order ? 'summary' : 'welcome';
      if (route() === '/operator') await loadOperatorOrders(true);
    });
  }

  function reconcileCurrent() {
    return runAction(async () => {
      await refreshCurrent();
      if (state.current.order) acceptCurrent(await request('/api/reconcile', {}));
      state.needsReconcile = false;
      navigate('/order', 'order-heading');
    }, 'The preview status now reflects the local server’s recorded state.');
  }

  function retryCurrent() {
    return runAction(async () => {
      acceptCurrent(await request('/api/retry', {}));
      state.phase = 'summary';
      byId('accept-terms').checked = false;
      navigate('/', 'summary-heading');
    }, 'Availability was checked on the same fictional order. Review the current sample date before checkout.');
  }

  async function getReport() {
    const response = await request('/api/report');
    if (typeof response.text !== 'string') throw new PreviewError('The preview report was not available as text.');
    state.report = response.text;
    state.reportOrder = state.current.order.id;
    return response.text;
  }

  function performOperatorAction(orderId, action) {
    return runAction(async () => {
      await request('/api/operator/action', { order_id: orderId, action });
      await loadOperatorOrders();
      await refreshCurrent();
      focusHeading('operator-heading');
    }, 'The local simulation was updated. No real payment, QA approval, or delivery occurred.');
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-route]');
    if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    const path = link.getAttribute('href');
    if (!ROUTES.has(path)) return;
    event.preventDefault();
    if (state.busy) return;
    if (path === '/') state.phase = state.current && state.current.order ? 'summary' : 'welcome';
    navigate(path);
    if (path === '/operator' && state.connected) runAction(async () => { await loadOperatorOrders(true); });
  });

  window.addEventListener('popstate', () => {
    clearError();
    render();
    if (route() === '/operator' && state.connected) runAction(async () => { await loadOperatorOrders(true); });
  });

  byId('dismiss-error').addEventListener('click', clearError);
  byId('reconnect').addEventListener('click', boot);
  byId('start-brief').addEventListener('click', () => startBrief());
  byId('hero-example').addEventListener('click', () => startBrief(true));
  byId('fill-example').addEventListener('click', () => startBrief(true));
  byId('edit-brief').addEventListener('click', () => startBrief(false, true));
  byId('handoff').addEventListener('input', updateCount);
  byId('brief-form').addEventListener('input', () => { state.submission = null; });

  byId('brief-form').addEventListener('submit', (event) => {
    event.preventDefault();
    clearFieldErrors();
    clearError();
    const brief = {
      workflow: byId('workflow').value,
      tools: byId('tools').value.trim(),
      handoff: byId('handoff').value.trim(),
      admin_only: byId('admin-only').checked,
      one_workflow: byId('one-workflow').checked,
      no_sensitive_data: byId('no-sensitive-data').checked,
      written_plan_only: byId('written-plan-only').checked,
    };
    const invalid = [];
    if (!Object.hasOwn(WORKFLOWS, brief.workflow)) { fieldError('workflow', 'workflow-error', 'Choose one workflow.'); invalid.push('workflow'); }
    if (brief.tools.length < 2 || brief.tools.length > 120) { fieldError('tools', 'tools-error', 'Describe the tools in 2–120 characters, without account details.'); invalid.push('tools'); }
    if (brief.handoff.length < 20 || brief.handoff.length > 600) { fieldError('handoff', 'handoff-error', 'Describe the handoff in 20–600 characters using fictional details.'); invalid.push('handoff'); }
    for (const [key, id] of [['admin_only', 'admin-only'], ['one_workflow', 'one-workflow'], ['no_sensitive_data', 'no-sensitive-data'], ['written_plan_only', 'written-plan-only']]) {
      if (!brief[key]) { fieldError(id, `${id}-error`, 'Confirm this scope statement before continuing.'); invalid.push(id); }
    }
    if (invalid.length) {
      announce('Review the highlighted brief fields and scope confirmations.');
      byId(invalid[0]).focus();
      return;
    }
    runAction(async () => {
      if (!state.submission) {
        if (!globalThis.crypto || typeof globalThis.crypto.randomUUID !== 'function') throw new PreviewError('This browser needs a secure local context with random UUID support. Open the preview on localhost in a current browser.');
        state.submission = crypto.randomUUID();
      }
      acceptCurrent(await request('/api/brief', { ...brief, submission_key: state.submission }));
      state.submission = null;
      state.phase = 'summary';
      byId('accept-terms').checked = false;
      navigate('/', 'summary-heading');
    }, 'The fictional brief is saved. Review its scope, sample date, and price.');
  });

  byId('open-checkout').addEventListener('click', () => {
    clearFieldErrors();
    if (!byId('accept-terms').checked) {
      fieldError('accept-terms', 'terms-error', 'Confirm that you understand this is a no-charge local simulation.');
      byId('accept-terms').focus();
      return;
    }
    runAction(async () => {
      acceptCurrent(await request('/api/checkout', { accept_preview_terms: true }));
      navigate('/checkout', 'checkout-heading');
    }, 'Fake checkout opened. No card details or live payment are involved.');
  });

  document.querySelectorAll('[data-outcome]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!state.current.order || !canPay(state.current.order)) return;
      runAction(async () => {
        acceptCurrent(await request('/api/pay', { outcome: button.dataset.outcome }));
        navigate('/order', 'order-heading');
      }, 'The selected fake-provider outcome was recorded. See the server-confirmed preview status below.');
    });
  });

  byId('refresh-order').addEventListener('click', () => runAction(async () => {
    await refreshCurrent();
    if (state.current.order && ['PAYMENT_PENDING', 'PAYMENT_REVIEW'].includes(state.current.order.state)) acceptCurrent(await request('/api/reconcile', {}));
  }, 'Preview order status refreshed from the local server.'));

  byId('view-report').addEventListener('click', () => runAction(async () => {
    await getReport();
    render();
    byId('report-text').focus();
  }, 'The private sample is open below.'));

  byId('download-report').addEventListener('click', () => runAction(async () => {
    const report = await getReport();
    const url = URL.createObjectURL(new Blob([report], { type: 'text/plain;charset=utf-8' }));
    const link = node('a');
    link.href = url;
    link.download = 'workflow-blueprint-preview.txt';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, 'The private sample text copy is ready to download.'));

  byId('revision-form').addEventListener('submit', (event) => {
    event.preventDefault();
    clearFieldErrors();
    const requestText = byId('revision-request').value.trim();
    if (requestText.length < 20 || requestText.length > 500) {
      fieldError('revision-request', 'revision-error', 'Describe one in-scope clarification in 20–500 characters.');
      byId('revision-request').focus();
      return;
    }
    runAction(async () => {
      acceptCurrent(await request('/api/revision', { request: requestText }));
      byId('revision-request').value = '';
      navigate('/order', 'order-heading');
    }, 'The sample clarification request is saved. Your delivered version stays available while it is prepared.');
  });

  byId('create-recovery').addEventListener('click', () => runAction(async () => {
    const response = await request('/api/recovery', {});
    if (typeof response.recovery_key !== 'string' || !response.recovery_key) throw new PreviewError('The local server did not return a private recovery key.');
    state.recoveryKey = response.recovery_key;
    renderRecovery(state.current.order);
    requestAnimationFrame(() => byId('recovery-key').focus());
  }, 'A private preview recovery key is shown below. Keep it somewhere private.'));

  byId('copy-recovery').addEventListener('click', async () => {
    if (!state.recoveryKey) return;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(state.recoveryKey);
      announce('Private recovery key copied. Keep it somewhere private.');
    } catch (_) {
      byId('recovery-key').focus();
      byId('recovery-key').select();
      announce('Automatic copy is unavailable. The recovery key is selected so you can copy it yourself.');
    }
  });

  byId('hide-recovery').addEventListener('click', () => {
    state.recoveryKey = null;
    renderRecovery(state.current.order);
    byId('create-recovery').focus();
    announce('The recovery key is hidden. It is not saved in local storage; this browser uses a private session cookie.');
  });

  byId('recover-form').addEventListener('submit', (event) => {
    event.preventDefault();
    clearFieldErrors();
    const key = byId('recover-key').value.trim();
    if (!key) {
      fieldError('recover-key', 'recover-error', 'Enter the private key for an existing preview order.');
      byId('recover-key').focus();
      return;
    }
    runAction(async () => {
      acceptCurrent(await request('/api/recover', { recovery_key: key }));
      byId('recover-key').value = '';
      state.recoveryKey = null;
      state.report = null;
      state.reportOrder = null;
      state.phase = 'summary';
      navigate('/order', 'order-heading');
    }, 'The fictional preview order was recovered on this browser. No email was sent.');
  });

  byId('operator-login').addEventListener('submit', (event) => {
    event.preventDefault();
    clearFieldErrors();
    const token = byId('operator-token').value.trim();
    if (!token) {
      fieldError('operator-token', 'operator-token-error', 'Enter the private token from the local preview server.');
      byId('operator-token').focus();
      return;
    }
    runAction(async () => {
      try {
        await request('/api/operator/login', { token });
      } finally {
        byId('operator-token').value = '';
      }
      await refreshCurrent();
      await loadOperatorOrders();
      renderOperator();
      focusHeading('operator-heading');
    }, 'The local operator workspace is open. All fulfillment and QA actions are simulated.');
  });

  byId('refresh-operator').addEventListener('click', () => runAction(async () => {
    await refreshCurrent();
    await loadOperatorOrders();
  }, 'Fictional orders refreshed from the local server.'));

  boot();
})();
