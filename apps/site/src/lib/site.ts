// The project is anonymous: its own email address is the only way to reach it.
// Set CONTACT_EMAIL (for example hello@<domain>) once the domain and Cloudflare Email Routing exist.
export const CONTACT_EMAIL: string = import.meta.env.CONTACT_EMAIL ?? '';

export const mailto = (subject: string) => `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}`;

// Preview builds (scripts/deploy-preview.mjs) are a frozen snapshot, so they must not promise weekly updates
export const WEEKLY: boolean = !import.meta.env.PREVIEW;
