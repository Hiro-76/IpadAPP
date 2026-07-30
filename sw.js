/* =======================================================================
   NAVLOG WORKSHEET — service worker
   オフライン起動のために必要な一式を丸ごとプリキャッシュする。
   キャッシュ名に VERSION を含めるので、VERSION を上げれば全ファイルを取り直す。
   ======================================================================= */
const VERSION = 'navlog-v1.0.0';
const CACHE   = VERSION;

/* sw.js からの相対パス。GitHub Pages のサブディレクトリ配信でもそのまま動く。 */
const ASSETS = [
  './',
  'index.html',
  'manifest.webmanifest',
  'vendor/pdf.min.js',
  'vendor/pdf.worker.min.js',
  'icons/apple-touch-icon.png',
  'icons/favicon-32.png',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    /* 1 つ失敗しても残りは入れる（アイコン欠けでアプリ全体を落とさない） */
    await Promise.all(ASSETS.map(async path => {
      try{
        const url = new URL(path, self.registration.scope).href;
        const res = await fetch(url, {cache: 'reload'});
        if(res.ok) await cache.put(url, res);
        else console.warn('[sw] precache skipped', path, res.status);
      }catch(err){
        console.warn('[sw] precache failed', path, err);
      }
    }));
    /* skipWaiting はページから明示的に指示された時だけ（作業中の自動リロードを防ぐ） */
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(n => n !== CACHE).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', event => {
  if(event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

/* ページ遷移: キャッシュの index.html を最優先（機内でも確実に開く） */
async function handleNavigation(request){
  const cache = await caches.open(CACHE);
  const cached = await cache.match(new URL('index.html', self.registration.scope).href);
  if(cached){
    /* オンラインなら裏で更新しておく */
    if(self.navigator.onLine !== false){
      fetch(request).then(res => {
        if(res && res.ok && res.type === 'basic'){
          cache.put(new URL('index.html', self.registration.scope).href, res.clone());
        }
      }).catch(() => {});
    }
    return cached;
  }
  try{
    return await fetch(request);
  }catch(err){
    return new Response(
      '<meta charset="utf-8"><p style="font:14px system-ui;padding:2em">' +
      'オフラインです。キャッシュがまだ作られていません。一度オンラインで開き直してください。</p>',
      {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}}
    );
  }
}

/* 静的ファイル: cache first（同一オリジンのみ） */
async function handleAsset(request){
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request, {ignoreSearch: true});
  if(cached) return cached;
  const res = await fetch(request);
  if(res && res.ok && res.type === 'basic'){
    cache.put(request, res.clone()).catch(() => {});
  }
  return res;
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if(req.method !== 'GET') return;

  let url;
  try{ url = new URL(req.url); }catch(err){ return; }
  if(url.origin !== self.location.origin) return;   /* 外部は素通し */

  if(req.mode === 'navigate'){
    event.respondWith(handleNavigation(req));
    return;
  }
  event.respondWith(handleAsset(req).catch(() => Response.error()));
});
