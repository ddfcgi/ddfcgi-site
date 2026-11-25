# ddfcgi.com: DNS records and cutover steps (Nov 24, 2026)

The domain stays registered at GoDaddy and its DNS stays on GoDaddy's nameservers (ns25/ns26.domaincontrol.com).
Only the website records change. Email (Google Workspace) and every other record stays exactly as it is.

## Records before the move (GoDaddy, 39 records)

Website (these change):

| Type | Name | Value |
|---|---|---|
| A | @ | 198.185.159.144 |
| A | @ | 198.185.159.145 |
| A | @ | 198.49.23.144 |
| A | @ | 198.49.23.145 |
| CNAME | www | ext-cust.squarespace.com. |
| CNAME | ngyrkr9yy5945t8al5db | verify.squarespace.com. (Squarespace's domain check; remove after Squarespace is cancelled) |

Everything else (unchanged): NS ns25/ns26.domaincontrol.com; SOA; five Google MX records (aspmx.l.google.com 1,
alt1/alt2 5, alt3/alt4 10); TXT SPF `v=spf1 include:_spf.google.com ~all`; TXT google-site-verification; TXT
logmein-verification-code (GoToAssist); CNAMEs calendar/docs/mail/sites (ghs.google.com), imap, smtp, m (ddfcgi.com),
ftp, _domainconnect, and the SMTP2GO sending records (em150580, link, s150580._domainkey); ten Google XMPP SRV records.

## Cutover (www is the main address)

1. GitHub: Settings > Pages > Source "GitHub Actions"; run the "Publish to GitHub Pages" workflow; custom domain
   `www.ddfcgi.com` (verify the domain for the ddfcgi organization first: one TXT record,
   `_github-pages-challenge-ddfcgi`).
2. GoDaddy, website records only:
   - Replace the four A records on `@` with GitHub Pages: 185.199.108.153, 185.199.109.153, 185.199.110.153,
     185.199.111.153.
   - Change `www` CNAME from `ext-cust.squarespace.com.` to `ddfcgi.github.io.`
   - Add the TXT record from step 1.
3. When GitHub shows the certificate is ready, tick "Enforce HTTPS".
4. Check: https://www.ddfcgi.com and https://ddfcgi.com (redirects to www), every page, the form, and that the MX,
   SPF and other records above are unchanged.

## Rollback

Put the four A records and the `www` CNAME back to the Squarespace values above (while the Squarespace site is
still paid for). Nothing else changes, so email is unaffected either way.
