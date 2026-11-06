// The project is anonymous: its own email address is the only way to reach it.
// Set CONTACT_EMAIL (for example hello@<domain>) once the domain and Cloudflare Email Routing exist.
export const CONTACT_EMAIL: string = import.meta.env.CONTACT_EMAIL ?? '';

// The site's own address, for links in posts and emails (astro.config.mjs SITE_URL)
export const SITE = (import.meta.env.SITE ?? 'https://galamseytracker.org').replace(/\/$/, '');

// The project's own X account (not a person's), which posts the weekly pictures
export const X_HANDLE = 'GalamseyTracker';
export const X_URL = `https://x.com/${X_HANDLE}`;

export const mailto = (subject: string) => `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}`;

// Hidden test copies (PREVIEW=1, scripts/deploy-site.mjs) are frozen snapshots, so they must not promise weekly updates
export const WEEKLY: boolean = !import.meta.env.PREVIEW;
