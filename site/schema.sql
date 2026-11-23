-- Daily page-view counts for the site Worker (site/worker.mjs). No cookies, no IPs.
CREATE TABLE IF NOT EXISTS page_views (day TEXT NOT NULL, path TEXT NOT NULL, referrer TEXT NOT NULL, country TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (day, path, referrer, country));
