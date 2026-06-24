const { test, expect } = require('@playwright/test');

test('loads the dashboard and switches profiles', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Noord Administratie' })).toBeVisible();
  const dashboardReset = page.getByRole('button', { name: 'Reset sandbox state' });
  await expect(dashboardReset).toHaveClass(/reset-button/);
  await expect(dashboardReset).toHaveCSS('background-color', 'rgb(178, 58, 72)');
  await expect(page.locator('.reset-note')).toHaveText('Resets your changes.');

  await page.getByRole('link', { name: 'Medium' }).click();
  await expect(page.getByRole('heading', { name: 'Maas & Co Administratie' })).toBeVisible();

  await page.getByRole('link', { name: 'Large' }).click();
  await expect(page.getByRole('heading', { name: 'Van der Berg & Co' })).toBeVisible();
});

test('filters flagged cases and opens a detail page', async ({ page }) => {
  await page.goto('/?profile=medium');
  await page.getByLabel('Status').selectOption('flagged');
  await page.getByRole('button', { name: 'Apply filters' }).click();

  await expect(page.getByText('Bakker Logistics B.V.')).toBeVisible();
  await page.getByRole('link', { name: 'Open' }).first().click();

  await expect(page.getByRole('heading', { name: 'Bakker Logistics B.V.' })).toBeVisible();
  await expect(page.locator('.warning-list').getByText('Foreign B2B reverse charge')).toBeVisible();
  await expect(page.locator('tbody .tx-status.flagged').first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sample PDF' }).first()).toHaveAttribute('href', /sample-document\/medium\//);
  await expect(page.getByText('No payload is prepared because this client still needs review')).toBeVisible();
});

test('corrects transaction issues and turns a review client ready', async ({ page }) => {
  await page.goto('/client/small/S-003');
  await expect(page.getByRole('heading', { name: 'Hein Reparatie' })).toBeVisible();
  const detailReset = page.getByRole('button', { name: 'Reset sandbox state' });
  await expect(detailReset).toHaveClass(/reset-button/);
  await expect(detailReset).toHaveCSS('background-color', 'rgb(178, 58, 72)');
  await expect(page.locator('.reset-note')).toHaveText('Resets your changes.');
  await expect(page.getByText('1 transaction issue(s) still open')).toBeVisible();
  const receiptRow = page.locator('tr.transaction-row', { hasText: 'S-T008' });
  await expect(receiptRow).toContainText('Missing');
  await expect(receiptRow).toContainText('Receipt ID');
  await expect(page.getByText('Fill column: Receipt')).toBeVisible();
  await expect(page.getByLabel('Receipt ID from PDF')).toBeVisible();

  const receiptReview = page.locator('.review-item', { hasText: 'receipt id label' });
  await receiptReview.getByRole('button', { name: 'Contact client if unreadable' }).click();
  await expect(page.getByText('Fallback to client')).toBeVisible();
  await expect(page.getByText('TS 520-78416')).toBeVisible();
  await page.getByRole('button', { name: 'Use client reply' }).click();

  await expect(page.locator('.pill.ready')).toBeVisible();
  await expect(receiptRow).toContainText('TS 520-78416');
  await expect(receiptRow).toContainText('Receipt ID entered');
  await expect(page.getByRole('button', { name: 'Approve and file this client' })).toBeVisible();
  await expect(page.locator('.payload-panel pre')).toContainText('No external API call is made.');

  await page.getByRole('button', { name: 'Reset sandbox state' }).click();
  await expect(page.locator('.pill.review')).toBeVisible();
  await expect(page.getByText('1 transaction issue(s) still open')).toBeVisible();
  await expect(page.getByPlaceholder('Example: TS 520-78416').first()).toBeVisible();
});

test('requests and analyses evidence for a flagged EU goods sale', async ({ page }) => {
  await page.goto('/client/large/L-003');
  await expect(page.getByRole('heading', { name: 'EuroFood Distributors' })).toBeVisible();
  await expect(page.locator('.pill.flagged')).toBeVisible();
  await expect(page.locator('.warning-list').getByText('EU goods sale needs VAT number evidence and transport proof. Related transaction: L-T007.')).toBeVisible();
  const evidenceRow = page.locator('tr.transaction-row', { hasText: 'L-T007' });
  await expect(evidenceRow).toContainText('EU_REVERSE');
  await expect(evidenceRow).toContainText('VAT to be accounted for by the recipient');
  await expect(evidenceRow).toContainText('Missing');
  await expect(evidenceRow).toContainText('Buyer VAT number evidence');
  await expect(evidenceRow).toContainText('Transport proof');

  await page.getByRole('button', { name: 'Contact company for evidence' }).click();
  await expect(page.getByText('Client reply')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Received evidence PDF' })).toHaveAttribute('href', /evidence-document\/large\/L-T007\.pdf/);
  await expect(evidenceRow).toContainText('PDF received, not analysed');

  await page.getByRole('button', { name: 'Analyse received PDF' }).click();
  await expect(page.getByText('Evidence accepted: Fiskal analysed the new PDF')).toBeVisible();
  await expect(page.locator('.pill.review')).toBeVisible();
  await expect(evidenceRow).toContainText('BE 0731.445.221');
  await expect(evidenceRow).toContainText('CMR-2026-Q2-118');

  await page.getByPlaceholder('Example: TS 520-78416').first().fill('KT 514-6B31');
  await page.getByRole('button', { name: 'Mark reviewed' }).first().click();
  await expect(page.locator('.pill.ready')).toBeVisible();
});

test('shows transport proof as not required for flagged services', async ({ page }) => {
  await page.goto('/client/small/S-005');
  await expect(page.getByRole('heading', { name: 'Kees Elektricien B.V.' })).toBeVisible();

  const serviceRow = page.locator('tr.transaction-row', { hasText: 'S-T013' });
  const table = page.locator('.table-wrap.flat table');
  const tableWrap = page.locator('.table-wrap.flat');
  const initialWrapWidth = await tableWrap.evaluate((element) => element.clientWidth);
  const initialTableWidth = await table.evaluate((element) => element.getBoundingClientRect().width);
  expect(initialTableWidth).toBeLessThanOrEqual(initialWrapWidth + 1);
  await expect(serviceRow).toContainText('EU_REVERSE');
  await expect(serviceRow).toContainText('VAT to be accounted for by the recipient');
  await expect(serviceRow).toContainText('Missing');
  await expect(serviceRow).toContainText('Buyer VAT number evidence');
  await expect(serviceRow).toContainText('Not required');
  await expect(serviceRow).toContainText('No goods shipment');

  await page.getByRole('button', { name: 'Contact company for evidence' }).click();
  await expect(page.getByText('Client reply')).toBeVisible();
  const evidenceThread = page.locator('.email-thread');
  await expect(evidenceThread).toContainText('Please send the buyer VAT-number evidence or corrected source document.');
  await expect(evidenceThread).not.toContainText('transport proof');
  const expandedTableWidth = await table.evaluate((element) => element.getBoundingClientRect().width);
  expect(expandedTableWidth).toBe(initialTableWidth);

  await page.getByRole('button', { name: 'Analyse received PDF' }).click();
  await expect(page.locator('.pill.ready')).toBeVisible();
  await page.goto('/?profile=small');
  const clientRow = page.locator('tbody tr', { hasText: 'Kees Elektricien B.V.' });
  await expect(clientRow).toContainText('Ready after resolved review items');
  await expect(clientRow).not.toContainText('Routine quarter');
});

test('approves a ready client and shows the payload', async ({ page }) => {
  await page.goto('/?profile=small');
  await page.getByRole('link', { name: 'Open' }).first().click();
  await expect(page.getByRole('heading', { name: 'Hennie Tuinaanleg' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to queue' })).toBeVisible();
  await expect(page.locator('.back-icon')).toHaveText('←');
  await expect(page.getByText('€2,770.00')).toBeVisible();

  await page.getByRole('button', { name: 'Approve and file this client' }).click();
  await expect(page.getByText('Filed after approval: 1.')).toBeVisible();
  await expect(page.locator('.kpi-ready')).toContainText('3');
  await expect(page.locator('.kpi-filed')).toContainText('2');
  await expect(page.locator('tbody tr', { hasText: 'Hennie Tuinaanleg' })).toContainText('Filed');

  await page.locator('tbody tr', { hasText: 'Hennie Tuinaanleg' }).getByRole('link', { name: 'Open' }).click();
  await expect(page.locator('.payload-panel pre')).toContainText('No external API call is made.');
  await expect(page.getByText('POST /ledger/moneybird/vat-entries')).toBeVisible();

  await page.getByRole('button', { name: 'Reset sandbox state' }).click();
  await expect(page.locator('.pill.ready')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve and file this client' })).toBeVisible();
});

test('bulk approval blocks review and flagged clients', async ({ page }) => {
  await page.goto('/?profile=small&status=review');
  await expect(page.locator('tbody .pill.review').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve and file selected clients' })).toBeVisible();
  await expect(page.locator('input[type="checkbox"]')).toHaveCount(0);
});