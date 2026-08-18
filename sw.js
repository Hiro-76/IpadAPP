/* =======================================================================
   NAVLOG WORKSHEET — service worker
   オフライン起動のために必要な一式を丸ごとプリキャッシュする。
   scope はサイト直下だが、面倒を見るのは下の ASSETS だけ。
   wind/ など別アプリのページ / ファイルには介入しない。
   キャッシュ名に VERSION を含めるので、VERSION を上げれば全ファイルを取り直す。
   ======================================================================= */
const VERSION = 'navlog-v1.5.0';
const CACHE   = VERSION;

/* sw.js からの相対パス。GitHub Pages のサブディレクトリ配信でもそのまま動く。 */
const ASSETS = [
  './',
  'index.html',
  'manifest.webmanifest',
  'vendor/pdf.min.js',
  'vendor/pdf.worker.min.js',
  'vendor/qrcode.js',
  'vendor/jsQR.js',
  'icons/apple-touch-icon.png',
  'icons/favicon-32.png',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon-maskable-512.png'
];

const abs   = path => new URL(path, self.registration.scope).href;
const INDEX = () => abs('index.html');
const ROOT  = () => abs('./');
/* 自分が面倒を見る URL 一覧（他アプリのファイルには手を出さない） */
const OWNED = () => ASSETS.map(abs);

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    /* 1 つ失敗しても残りは入れる（アイコン欠けでアプリ全体を落とさない） */
    await Promise.all(ASSETS.map(async path => {
      try{
        const res = await fetch(abs(path), {cache: 'reload'});
        if(res.ok) await cache.put(abs(path), res);
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
    /* 自分の古いキャッシュだけ消す（他アプリのキャッシュは残す） */
    await Promise.all(names.filter(n => n !== CACHE && n.startsWith('navlog-'))
                           .map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', event => {
  if(event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

function offlinePage(){
  return new Response(
    '<meta charset="utf-8"><p style="font:14px system-ui;padding:2em">' +
    'オフラインです。キャッシュがまだ作られていません。一度オンラインで開き直してください。</p>',
    {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}}
  );
}

/* ページ遷移: 自分のページならキャッシュの index.html を最優先（機内でも確実に開く） */
async function handleNavigation(request){
  const bare = request.url.split('#')[0].split('?')[0];
  const cache = await caches.open(CACHE);

  if(bare === ROOT() || bare === INDEX()){
    const cached = await cache.match(INDEX());
    if(cached){
      /* オンラインなら裏で更新しておく */
      if(self.navigator.onLine !== false){
        fetch(request).then(res => {
          if(res && res.ok && res.type === 'basic') cache.put(INDEX(), res.clone());
        }).catch(() => {});
      }
      return cached;
    }
  }
  /* wind/ などは各アプリの service worker に任せる */
  try{
    return await fetch(request);
  }catch(err){
    return (await cache.match(request, {ignoreSearch: true})) || offlinePage();
  }
}

/* 静的ファイル: 自分の管理対象だけキャッシュ優先で返す */
async function handleAsset(request){
  const bare = request.url.split('#')[0].split('?')[0];
  const cache = await caches.open(CACHE);
  if(OWNED().includes(bare)){
    const cached = await cache.match(bare);
    if(cached) return cached;
    const res = await fetch(request);
    if(res && res.ok && res.type === 'basic') cache.put(bare, res.clone()).catch(() => {});
    return res;
  }
  try{
    return await fetch(request);
  }catch(err){
    return (await cache.match(request, {ignoreSearch: true})) || Response.error();
  }
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
