// Cookieless, IP-free aggregated page view counter for Footnote One static site.
// Only HTML and Markdown/llms page routes run through this Worker (see wrangler.jsonc run_worker_first).
// Static assets (/assets/*, images, fonts) bypass the Worker completely.
export default {
  async fetch(request, env, ctx) {
    const response = await env.ASSETS.fetch(request);

    if (request.method === "GET" && response.status >= 200 && response.status < 400 && env.DB) {
      const url = new URL(request.url);
      let referrerHost = "direct";
      const ref = request.headers.get("referer");
      if (ref) {
        try {
          const parsed = new URL(ref);
          referrerHost = parsed.hostname === url.hostname ? "internal" : parsed.hostname;
        } catch {
          referrerHost = "invalid";
        }
      }
      const day = new Date().toISOString().slice(0, 10);
      const country = request.cf?.country || "XX";

      ctx.waitUntil(
        env.DB.prepare(
          "INSERT INTO page_views (day, path, referrer, country, count) VALUES (?, ?, ?, ?, 1) ON CONFLICT(day, path, referrer, country) DO UPDATE SET count = count + 1"
        )
          .bind(day, url.pathname, referrerHost, country)
          .run()
          .catch(() => {})
      );
    }

    return response;
  },
};
