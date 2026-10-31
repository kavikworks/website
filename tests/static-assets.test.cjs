const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const publicPaths = [
  'index.html', 'intake.html', '404.html', 'privacy.html', 'terms.html', 'refunds.html',
  'favicon.svg', 'site.css', 'commercial-pages.css', 'workflow-check.js',
  'robots.txt', 'llms.txt', 'sitemap.xml',
  'ai-email-triage/index.html', 'lead-response-automation/index.html',
  'guides/index.html',
  'guides/stop-missing-calls-hvac-plumbing.html',
  'guides/job-intake-scheduling-without-new-software.html',
  'guides/estimate-follow-up-small-contractors.html',
  'guides/maintenance-requests-small-property-portfolio.html',
  'guides/recurring-cleaning-client-schedule.html',
  'guides/reduce-no-shows-home-service.html',
  'guides/after-hours-calls-electrical-handyman.html',
  'guides/lead-response-cost.html', 'guides/lead-response-automation-vs-crm.html',
  'build-concepts/index.html', 'build-concepts/cpa-client-intake-triage.html',
  'build-concepts/financial-advisor-inquiry-routing.html',
  'build-concepts/hvac-lead-response.html',
  'build-concepts/insurance-quote-claims-routing.html',
  'build-concepts/law-firm-client-intake.html',
  'build-concepts/medical-practice-inquiry-routing.html',
  'build-concepts/msp-support-ticket-routing.html',
  'build-concepts/property-management-inquiries.html',
  'build-concepts/real-estate-lead-routing.html',
  'build-concepts/staffing-recruiting-inquiry-routing.html',
  'sample-workflow/index.html', 'sample-workflow/workflow-blueprint-sample.md',
  'sample-workflow/workflow-blueprint-sample.pdf',
];

// Cloudflare documents .assetsignore as using .gitignore syntax. Exercise that
// syntax in a disposable repository; never alter this checkout's ignore rules.
function withAssetPolicy(fn) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'kavik-assets-test-'));
  try {
    execFileSync('git', ['init', '--quiet', temp]);
    fs.copyFileSync(path.join(root, '.assetsignore'), path.join(temp, '.gitignore'));
    const excluded = (candidate) => {
      const result = spawnSync('git', [
        '-c', 'core.excludesFile=/dev/null', 'check-ignore', '--quiet', '--no-index', candidate,
      ], { cwd: temp });
      assert.ifError(result.error);
      assert.ok([0, 1].includes(result.status), result.stderr.toString());
      return result.status === 0;
    };
    fn(excluded);
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

test('static-only configuration preserves production routing and disables version URLs', () => {
  const config = JSON.parse(fs.readFileSync(path.join(root, 'wrangler.jsonc'), 'utf8'));
  assert.deepEqual(config, {
    $schema: 'node_modules/wrangler/config-schema.json',
    name: 'website',
    compatibility_date: '2026-10-06',
    workers_dev: true,
    preview_urls: false,
    observability: { enabled: true },
    assets: { directory: '.', not_found_handling: '404-page' },
  });
});

test('all 39 existing public assets are included, including both sample downloads and the not-found page', () => {
  assert.equal(publicPaths.length, 39);
  withAssetPolicy((excluded) => {
    for (const candidate of publicPaths) {
      assert.ok(fs.statSync(path.join(root, candidate)).isFile(), candidate);
      assert.equal(excluded(candidate), false, candidate);
    }
  });
});

test('every other tracked repository file is excluded', () => {
  const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: root })
    .toString().split('\0').filter(Boolean);
  withAssetPolicy((excluded) => {
    for (const candidate of tracked.filter((file) => !publicPaths.includes(file))) {
      assert.equal(excluded(candidate), true, candidate);
    }
  });
});

test('the not-found page links home, the workflow check, the sample, and support', () => {
  const html = fs.readFileSync(path.join(root, '404.html'), 'utf8');
  assert.match(html, /href="\/"/);
  assert.match(html, /href="\/intake"/);
  assert.match(html, /href="\/sample-workflow\/"/);
  assert.match(html, /Support: <a href="mailto:josh@kavikworks.com">josh@kavikworks.com<\/a>/);
});

test('every public HTML page lists support email in the footer', () => {
  for (const candidate of publicPaths.filter((file) => file.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(root, candidate), 'utf8');
    assert.match(html, /Support: <a href="mailto:josh@kavikworks.com">josh@kavikworks.com<\/a>/, candidate);
  }
});

test('new files, private files, and dotfiles fail closed even under public directories', () => {
  const candidates = [
    'AGENTS.md', 'wrangler.jsonc', '.assetsignore', '.gitignore', '.env',
    '.env.production', '.git/HEAD', '.git/config', '.wrangler/tmp/worker.js',
    '.agents/skills/private.md', '.codex/private.json',
    'scripts/buying_intent_validator.py', 'scripts/check_site.py',
    'tests/static-assets.test.cjs', 'tests/fixtures/buying-intent-synthetic.json',
    'docs/buying-intent-discovery.md', 'wiki/entities/private.md',
    'automations/.env.example', 'templates/workflow-blueprint.md',
    'node_modules/wrangler/package.json', 'dist/private.json', 'private.html',
    'sample-workflow/private.html', 'sample-workflow/.env',
    'sample-workflow/.private/notes.txt', 'sample-workflow/notes.md',
    'sample-workflow/private/workflow-blueprint-sample.pdf',
    'build-concepts/internal.html', 'build-concepts/.git/config',
    'guides/private.json', 'guides/internal/lead-response-cost.html',
    'ai-email-triage/internal.js', 'lead-response-automation/.secret',
  ];
  withAssetPolicy((excluded) => {
    for (const candidate of candidates) {
      assert.equal(excluded(candidate), true, candidate);
    }
  });
});
