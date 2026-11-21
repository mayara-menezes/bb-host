# Original site analysis (bbhost.com.br, November 2026)

## Original stack
- **Odoo 18 (Website + eCommerce)** behind Cloudflare.
- Visual base: **Bootstrap 5** + **Font Awesome 4.7** (from Odoo) + custom CSS with a `bb-*` prefix.
- Fonts: **Inter** (body), **Assistant 700** (headings, Odoo theme default), **Source Sans Pro** (Odoo base).
- Light/dark theme through the `html[data-bb-theme]` attribute, saved in `localStorage["bb-theme"]`.

## Design tokens (light theme)
| Token | Value |
| --- | --- |
| `--bb-bg` | `#f5f8fc` |
| `--bb-card` | `#ffffff` |
| `--bb-fg` / `--bb-fg-strong` | `#1e293b` / `#0b1220` |
| `--bb-muted` | `#56657c` |
| `--bb-primary` | `#3b82f6` (hover `#2563eb`) |
| `--bb-grad` | `linear-gradient(135deg, #2563eb, #38bdf8)` |
| `--bb-radius` | `0.75rem` (cards `1rem`) |

Dark theme: background `#080c16`, cards `#101a30`, text `#e8eef7`.

## Pages
| Route | Content | Interactivity |
| --- | --- | --- |
| `/` | Hero, 4 services, DDoS block with stats, CTA | — |
| `/vps` | vCPU/RAM/disk/OS builder | Price = vCPU×15 + GB×10 + disk×0.60 |
| `/dedicated` | Catalog with 10 servers | Sorting (GET), "notify me" |
| `/colocation` | Estimate by U and watts | R$150/U + R$0.64/W, multiple rows |
| `/mitigation` | Clean-traffic slider + delivery mode | Builds a WhatsApp message |
| `/about` | Numbers, infrastructure, network, Anti-DDoS, company | — |
| `/contact` | Odoo's default contact form (still with placeholder data on the original) | — |

Global elements: Black Friday promo banner (copyable coupon), theme button
(bottom-left corner), chat button (bottom-right corner), four-column footer.

## Customer area (logged in)
Dashboard with credit balance and counters (services, open invoices, contracts, IP blocks),
invoices, contracts, IP blocks, auto-pay, due-date change, support tickets with 21 categories,
sub-accounts with roles and permissions, 2FA, and a colocation quote reserved for verified accounts.
The dedicated server "Configure" page adds paid options (10 Gbps unmetered bandwidth,
IP blocks from /29 to /24, partitioning), its own OS list, panel license, hostname and SSH key.

## How the analysis was done

The original site sits behind Cloudflare, so data was collected through the browser itself:
screenshots of every section, reading the DOM and measuring the CSS rules with the `bb-*`
prefix (colors, spacing, radii, shadows, gradients). Those values became the design tokens in
`static/src/input.css`; the replica's front end was then rebuilt from scratch with Tailwind CSS.
The raw material (HTML, Odoo's full CSS and screenshots) was kept out of the repository.

Then the logged-in customer area was browsed in read-only mode to find out what the models
needed to store: dedicated server paid options, IP blocks, document types, support plan,
account verification, invoices, credit and tickets.
