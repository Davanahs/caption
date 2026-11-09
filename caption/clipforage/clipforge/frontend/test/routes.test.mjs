import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appDir = path.resolve(__dirname, '../app');

test('Route Integrity: All Sidebar routes exist as valid Next.js app pages', () => {
  const sidebarRoutes = [
    { name: 'Dashboard', path: '/', pageFile: path.join(appDir, 'page.tsx') },
    { name: 'Podcasts', path: '/podcasts', pageFile: path.join(appDir, 'podcasts/page.tsx') },
    { name: 'Upload Studio', path: '/studio', pageFile: path.join(appDir, 'studio/page.tsx') },
    { name: 'Clips', path: '/clips', pageFile: path.join(appDir, 'clips/page.tsx') },
    { name: 'Analytics', path: '/analytics', pageFile: path.join(appDir, 'analytics/page.tsx') },
    { name: 'Automation', path: '/automation', pageFile: path.join(appDir, 'automation/page.tsx') },
    { name: 'My YouTube Channels', path: '/youtube-channels', pageFile: path.join(appDir, 'youtube-channels/page.tsx') },
    { name: 'Publish', path: '/publish', pageFile: path.join(appDir, 'publish/page.tsx') },
    { name: 'Settings', path: '/settings', pageFile: path.join(appDir, 'settings/page.tsx') },
  ];

  for (const route of sidebarRoutes) {
    assert.ok(
      fs.existsSync(route.pageFile),
      `Expected page file for route "${route.name}" (${route.path}) at ${route.pageFile}`
    );
    const content = fs.readFileSync(route.pageFile, 'utf8');
    assert.ok(
      content.includes('export default'),
      `Page for route "${route.name}" must export a default React component`
    );
  }
});

test('Dead Route Prevention: No page navigates to nonexistent /jobs route', () => {
  const pagesToCheck = [
    path.join(appDir, 'automation/page.tsx'),
    path.join(appDir, 'page.tsx'),
    path.join(appDir, 'clips/page.tsx'),
    path.join(appDir, 'publish/page.tsx'),
  ];

  for (const file of pagesToCheck) {
    if (fs.existsSync(file)) {
      const content = fs.readFileSync(file, 'utf8');
      assert.ok(
        !content.includes("router.push('/jobs')") && !content.includes('router.push("/jobs")'),
        `File ${path.basename(file)} should not push to nonexistent '/jobs' route (should use '/')`
      );
    }
  }
});
