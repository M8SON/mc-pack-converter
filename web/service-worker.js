// The build prepends a content hash and the SHA-256 of every deployed file.
const PREFIX = "mc-pack-converter-" + self.registration.scope + "-";
const CACHE = PREFIX + VERSION;
const urls = new Map(Object.entries(FILES).map(([path, hash]) =>
  [new URL(path, self.registration.scope).href, hash]));

async function verified(response, hash) {
  if (!response || !response.ok) return false;
  const digest = await crypto.subtle.digest("SHA-256", await response.clone().arrayBuffer());
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("") === hash;
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const previous = await caches.keys();
    for (const [url, hash] of urls) {
      let response = await cache.match(url);
      if (await verified(response, hash)) continue;
      for (const name of previous.filter(name => name.startsWith(PREFIX) && name !== CACHE)) {
        response = await (await caches.open(name)).match(url);
        if (await verified(response, hash)) break;
      }
      if (!await verified(response, hash)) response = await fetch(url, { cache: "no-store" });
      if (!await verified(response, hash)) throw new Error(`Integrity check failed: ${url}`);
      await cache.put(url, response);
    }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith(PREFIX) && name !== CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.href === self.registration.scope) url.pathname += "index.html";
  if (!urls.has(url.href)) return;
  event.respondWith((async () => {
    const response = await (await caches.open(CACHE)).match(url.href);
    return response || fetch(event.request);
  })());
});
