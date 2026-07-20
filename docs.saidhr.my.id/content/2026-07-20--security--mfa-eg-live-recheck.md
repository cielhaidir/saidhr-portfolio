---
title: "Pemeriksaan Live Keamanan MFA-EG"
date: 2026-07-20
category: security
status: partial
tags: [security, live-check, headers, oidc, saml, mfa]
---

# Pemeriksaan Live Keamanan MFA-EG

## Ringkasan Eksekutif

- Host `https://mfa-eg.eguard.id/` dapat di-resolve dan merespons HTTPS dengan HTTP 200.
- TLS dan security headers utama terdeteksi aktif, termasuk HSTS, CSP, X-Frame-Options, X-Content-Type-Options, dan Permissions-Policy.
- Endpoint health/readiness aktif dan endpoint SCIM menolak request tanpa bearer token dengan HTTP 401.
- Temuan live sebelum remediation: endpoint `/metrics` publik dan mengungkap route telemetry serta label build `version="dev"`.
- Remediasi source telah diterapkan: `/metrics` memerlukan `METRICS_BEARER_TOKEN`, label build `dev` dihapus, dan production mode gagal start bila token belum dikonfigurasi. Status live menunggu deployment dan retest.
- Endpoint `/openapi.yaml`, OIDC discovery, JWKS, dan SAML metadata juga publik. Ini dapat sesuai desain, tetapi perlu dipastikan bahwa spesifikasi dan metadata tidak mengungkap informasi sensitif.
- Probe OIDC dengan client yang tidak terdaftar dan redirect URI eksternal menampilkan form login HTTP 200. Ini mengonfirmasi bahwa validasi tersebut belum dilakukan pada tahap GET; dampak penuh setelah autentikasi tidak diuji karena tidak menggunakan kredensial produksi.

## Tujuan dan Ruang Lingkup

- **Tujuan:** memverifikasi deployment live yang benar dan mengecek kontrol keamanan pasif serta perilaku unauthenticated.
- **Cakupan:** DNS, HTTPS/TLS, response headers, health/readiness, metrics, OpenAPI, OIDC/SAML metadata, SCIM unauthenticated access, dan OIDC authorization pre-authentication.
- **Di luar cakupan:** login dengan kredensial nyata, MFA approval, code exchange yang memerlukan akun, brute force, fuzzing agresif, perubahan data, dan pengujian destruktif.

## Hasil / Perubahan

- DNS `mfa-eg.eguard.id` berhasil di-resolve ke Cloudflare anycast IP.
- HTTPS mengembalikan HTTP/2 200 untuk root, login, health, readiness, OIDC discovery, JWKS, SAML metadata, OpenAPI, dan metrics.
- Sertifikat TLS yang terlihat memiliki SAN `eguard.id` dan `*.eguard.id`; issuer adalah Google Trust Services WE1.
- HTTP port 80 merespons langsung HTTP 200 dan tidak memberikan redirect HTTPS pada pemeriksaan ini. Karena sertifikat/HSTS hanya berlaku setelah HTTPS, edge sebaiknya dikonfigurasi untuk redirect HTTP ke HTTPS atau menolak HTTP.

## Temuan dan Dampak

| Prioritas | Temuan | Status source | Status live |
|---|---|---|---|
| Medium | HTTP port 80 merespons HTTP 200 tanpa redirect ke HTTPS | Belum berubah; ini kontrol edge/proxy, bukan kode backend. | **Terbuka** |
| Low | `/metrics` publik dan `version="dev"` | **Tertutup** — bearer token wajib, label build dihapus, startup production mewajibkan token. | Menunggu deploy/retest |
| Medium, perlu validasi penuh | OIDC GET menerima `client_id` tidak terdaftar dan redirect URI eksternal | **Tertutup** — authorize/verify/token hanya menerima aplikasi aktif dengan redirect URI exact-match; token endpoint juga memeriksa client secret. | Menunggu deploy/retest |
| Info/Review | `/openapi.yaml`, OIDC discovery, JWKS kosong, dan SAML metadata publik | Belum berubah; perlu keputusan produk/operasional atas kebutuhan publikasi. | Terkonfirmasi live |
| Info | TLS certificate wildcard | Tidak berubah. | Tidak ada temuan |

## Bukti dan Verifikasi

- `getent ahosts mfa-eg.eguard.id` → host resolve ke Cloudflare IP `172.67.211.2` dan `104.21.69.178` serta alamat IPv6.
- `curl -skS https://mfa-eg.eguard.id/` → `HTTP/2 200`, halaman MFA Access Gateway.
- `GET /healthz` → `HTTP/2 200`, `{"status":"ok"}`.
- `GET /readyz` → `HTTP/2 200`, `{"status":"ready"}`.
- `GET /scim/v2/ServiceProviderConfig` tanpa Authorization → `HTTP/2 401`, `missing bearer token`.
- `GET /metrics` → `HTTP/2 200`, `content-type: text/plain; version=0.0.4`, route counters dan `mfa_be_build_info{version="dev"} 1` terlihat.
- `GET /openapi.yaml` → `HTTP/2 200`, sekitar 31 KB OpenAPI YAML.
- `GET /.well-known/openid-configuration` → `HTTP/2 200`, issuer `https://mfa-eg.eguard.id` dan endpoint OIDC terlihat.
- `GET /oidc/jwks.json` → `HTTP/2 200`, `{"keys":[]}`.
- `GET /saml/metadata` → `HTTP/2 200`, SAML metadata menunjuk ke host `mfa-eg.eguard.id`.
- `GET /oidc/authorize?client_id=unregistered-probe&redirect_uri=https://example.com/callback&state=probe-state` → `HTTP/2 200` dan form login ditampilkan. Tidak ada kredensial yang dikirim.
- Security headers HTTPS yang terdeteksi: `Strict-Transport-Security: max-age=31536000; includeSubDomains`, CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, dan Permissions-Policy.
- `curl -I http://mfa-eg.eguard.id/` → `HTTP/1.1 200 OK`, bukan redirect HTTPS.
- TLS summary → sertifikat wildcard `*.eguard.id`, issuer Google Trust Services WE1, masa berlaku terdeteksi 2026-06-07 sampai 2026-09-05.

## Risiko, Batasan, dan Asumsi

- Pengujian dilakukan secara pasif dan tanpa kredensial produksi.
- Probe OIDC hanya membuktikan perilaku tahap authorization GET. Belum dapat disimpulkan bahwa authorization code benar-benar dikirim ke domain eksternal tanpa menyelesaikan login dan MFA.
- Header yang terlihat berasal dari jalur Cloudflare dan origin; konfigurasi internal yang tidak terpapar tidak dinilai.
- Cookie Secure belum dapat dinilai dari halaman GET yang tidak mengeluarkan session cookie.
- Status report tetap `partial` karena alur autentikasi dan validasi post-auth belum diuji.

## Rekomendasi / Tindak Lanjut

- [ ] Konfigurasikan HTTP port 80 untuk redirect permanen ke HTTPS atau menolak request HTTP.
- [x] Batasi `/metrics` dengan `METRICS_BEARER_TOKEN`; label build `version="dev"` dihapus dari source.
- [x] Tolak `client_id` yang tidak terdaftar sebelum form login ditampilkan.
- [x] Cocokkan `redirect_uri` dengan allowlist client secara exact-match; token endpoint juga memverifikasi client secret.
- [ ] Deploy konfigurasi production (`METRICS_BEARER_TOKEN`, `TRUSTED_PROXY_CIDRS`) dan uji dengan akun test non-produksi bahwa authorize, code issuance, dan token exchange menolak client/redirect mismatch.
- [ ] Review apakah `/openapi.yaml`, SAML metadata, OIDC discovery, dan JWKS perlu publik; jika tidak, batasi aksesnya.
- [ ] Ulangi pemeriksaan cookie setelah deploy dengan alur login test yang sah, terutama atribut `Secure`, `HttpOnly`, dan `SameSite`.

## Changelog

- 2026-07-20 — Pemeriksaan live dipindahkan ke host `mfa-eg.eguard.id` setelah host tersebut berhasil di-resolve.
- 2026-07-20 — Ditambahkan bukti response headers, endpoint unauthenticated, metrics, OIDC pre-auth, dan HTTP downgrade behavior.
- 2026-07-20 — Status remediation source ditambahkan; verifikasi live tetap menunggu deployment dan retest.

## Referensi Internal

- Source: `/home/said/mfa-be`
- Report audit source/dependency: `/home/said/mfa-be/security-audit-report.md`
- URL yang diuji: `https://mfa-eg.eguard.id/`

Belum dipublikasikan ke URL dokumentasi publik.

---

## Catatan Publikasi

Dokumen ini tidak memuat kredensial, token, password, data pribadi mentah, atau payload eksploitasi operasional.
