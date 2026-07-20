---
title: "Recheck Keamanan Setelah Patch MFA-EG"
date: 2026-07-20
category: security
status: partial
tags: [security, recheck, oidc, dependencies, mfa]
---

# Recheck Keamanan Setelah Patch MFA-EG

## Ringkasan Eksekutif

- Commit patch awal `3164e23` telah direcheck; dua regresi source yang ditemukan pada recheck ini (binding `ClientID` authorization code dan validasi state OIDC) sudah diperbaiki pada perubahan lanjutan yang belum dideploy.
- `go test ./...` berhasil untuk seluruh package dan `govulncheck ./...` tidak menemukan vulnerability pada call path aplikasi.
- Dependency yang sebelumnya terdeteksi vulnerable sudah dinaikkan ke `pgx/v5 v5.9.2` dan `goxmldsig v1.6.0`.
- Deployment `https://mfa-eg.eguard.id/` masih menunjukkan konfigurasi lama pada beberapa kontrol: HTTP port 80 mengembalikan HTTP 200, `/metrics` masih publik, dan probe OIDC client tidak terdaftar masih menampilkan form login HTTP 200.
- Kesimpulan: perbaikan source lokal tervalidasi, tetapi belum terdeploy atau belum terlihat efeknya pada production. Production tidak dapat dianggap aman sebelum build terbaru dan konfigurasi production diterapkan lalu diretest.

## Tujuan dan Ruang Lingkup

- **Tujuan:** memisahkan hasil patch source lokal dari perilaku deployment production.
- **Cakupan:** git state, source review pada OIDC/cookie/proxy, Go tests, govulncheck, dan pemeriksaan pasif deployment.
- **Di luar cakupan:** kredensial production, MFA approval, code exchange dengan akun nyata, brute force, perubahan data, dan eksploitasi destruktif.

## Hasil / Perubahan

- Commit terbaru source: `3164e23 fix: harden OIDC and security controls`.
- `go.mod` sekarang memuat `github.com/jackc/pgx/v5 v5.9.2` dan `github.com/russellhaering/goxmldsig v1.6.0`.
- Cookie helper lokal sekarang menetapkan `Secure: true`.
- Security header HSTS lokal sekarang bergantung pada TLS atau forwarded proto dari trusted proxy.
- OIDC lokal melakukan lookup registered client/redirect sebelum login, mewajibkan state non-kosong pada authorize dan verify, serta memeriksa client credentials pada token endpoint.
- Authorization code sekarang menyimpan `ClientID`, lalu token endpoint memeriksa kecocokan client ID, redirect URI, dan client secret.
- Perubahan lanjutan recheck saat ini belum committed/deployed; report lokal `security-audit-report.md` tetap tidak di-track.

## Temuan dan Dampak

| Prioritas | Temuan | Dampak | Status |
|---|---|---|---|
| Selesai | Dependency `pgx` dan `goxmldsig` di-upgrade | Vulnerability reachable sebelumnya tidak lagi terdeteksi oleh govulncheck. | Terverifikasi di source lokal |
| Selesai | Cookie helper lokal menambahkan `Secure: true` | Mengurangi risiko cookie dikirim melalui HTTP. | Terverifikasi di source lokal; belum terlihat di production karena belum ada login test |
| Selesai | Authorization code menyimpan dan token endpoint memvalidasi `ClientID` | Mencegah exchange oleh client berbeda dan memulihkan exchange legitimate untuk client asal. | Terverifikasi di source lokal; belum deployed |
| Medium | State OIDC sekarang wajib non-kosong, tetapi nilai state tetap berasal dari client dan belum disimpan sebagai browser-bound server transaction | Mencegah flow tanpa state, tetapi perlindungan login-CSRF/account confusion belum setara state transaction yang diikat server-side. | **Sebagian diperbaiki** di source lokal; belum deployed |
| Medium | Production HTTP port 80 mengembalikan HTTP 200 tanpa redirect | First request melalui HTTP tidak dipaksa ke HTTPS; HSTS tidak melindungi first visit. | Terkonfirmasi live; patch backend tidak mengubah edge |
| Low | Production `/metrics` masih publik dan menampilkan route counters serta `version="dev"` | Membantu reconnaissance dan mengungkap informasi operasional. | Terkonfirmasi live |
| Medium, perlu validasi penuh | Production OIDC GET dengan client tidak terdaftar dan redirect eksternal masih menampilkan form login | Menunjukkan production belum menjalankan validasi source terbaru, atau route tersebut belum menggunakan patch. Dampak post-auth tidak diuji. | Terkonfirmasi tahap pre-auth live |

## Bukti dan Verifikasi

- `/home/said/.local/opt/go/bin/go test ./...` → PASS untuk seluruh package.
- `/home/said/.local/opt/go/bin/go run golang.org/x/vuln/cmd/govulncheck@latest ./...` → `No vulnerabilities found`; scanner menyebut 0 vulnerability pada package yang di-import/call path aplikasi.
- `git log -3 --oneline` → commit terbaru `3164e23 fix: harden OIDC and security controls`.
- `go.mod` → `pgx/v5 v5.9.2`, `goxmldsig v1.6.0`.
- Source lokal `cmd/server/main.go` → registered OIDC client/redirect diperiksa sebelum form login; state non-kosong juga diwajibkan pada authorize dan verify.
- Source lokal `cmd/server/main.go` → object authorization code sekarang dibuat dengan `ClientID`, `RedirectURI`, dan expiry.
- Source lokal `cmd/server/main.go` → token endpoint memerlukan registered client, client secret, redirect URI, serta kecocokan `stored.ClientID`.
- Source lokal `cmd/server/main.go:2395-2403` → cookie helper memakai `Secure: true`.
- `GET https://mfa-eg.eguard.id/metrics` → HTTP 200; metrics publik dan label `mfa_be_build_info{version="dev"} 1` masih terlihat.
- `GET https://mfa-eg.eguard.id/oidc/authorize?client_id=unregistered-probe&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&state=probe-state` → HTTP 200 dan form login masih ditampilkan.
- `HEAD http://mfa-eg.eguard.id/` → HTTP 200; tidak redirect ke HTTPS.
- HTTPS production masih mengembalikan HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, dan Permissions-Policy.

## Risiko, Batasan, dan Asumsi

- Production belum dapat dianggap memakai patch lokal hanya karena source lokal sudah diperbaiki. Bukti runtime menunjukkan beberapa behavior lama masih aktif.
- Tidak ada deployment action yang dilakukan dalam recheck ini.
- Probe OIDC live hanya membuktikan tahap GET/pre-auth. Tidak ada kredensial atau MFA production yang digunakan.
- `govulncheck` tetap mencatat vulnerability pada sebagian module yang diperlukan tetapi tidak reachable dari call path aplikasi; hasil ini bukan blocker reachable pada recheck ini, namun dependency hygiene tetap perlu dipantau.

## Rekomendasi / Tindak Lanjut

- [x] Perbaiki assignment authorization code agar menyimpan `ClientID: clientID`.
- [x] Wajibkan state OIDC non-kosong pada authorization dan verification flow.
- [x] Jalankan regression test state, lalu `go test ./...` dan `govulncheck ./...`; seluruhnya berhasil, dengan 0 vulnerability reachable.
- [ ] Implementasikan state OIDC yang random dan server-side/browser-bound, lalu ikat ke transaction, client, dan redirect sebelum callback (hardening lanjutan).
- [ ] Commit dan deploy build terbaru yang memuat perbaikan recheck ini ke environment target.
- [ ] Setelah deploy, ulangi probe live dan pastikan unknown client/redirect ditolak sebelum form login (HTTP 400/401).
- [ ] Konfigurasikan port 80 untuk redirect permanen ke HTTPS atau menolak request.
- [ ] Batasi `/metrics` ke jaringan monitoring internal atau autentikasi dan hilangkan `version="dev"` dari production.
- [ ] Verifikasi cookie session melalui login test yang sah dan pastikan `Secure`, `HttpOnly`, serta `SameSite` benar.

## Changelog

- 2026-07-20 — Recheck source setelah commit hardening OIDC/security.
- 2026-07-20 — Tests dan govulncheck dijalankan ulang.
- 2026-07-20 — Production endpoint diuji ulang dan dipisahkan dari hasil source lokal.
- 2026-07-20 — Temuan assignment `ClientID` dan state OIDC diremediasi pada source lokal; seluruh test dan govulncheck ulang berhasil. Perubahan menunggu commit/deploy.

## Referensi Internal

- Source: `/home/said/mfa-be`
- Commit patch: `3164e23`
- URL production: `https://mfa-eg.eguard.id/`
- Report teknis: `/home/said/mfa-be/security-audit-report.md`

Belum dipublikasikan ke URL dokumentasi publik.

---

## Catatan Publikasi

Dokumen ini tidak memuat credentials, token, password, data pribadi mentah, atau payload eksploitasi operasional.
