---
title: "Retest Keamanan MFA Backend"
date: 2026-07-20
category: security
status: partial
tags: [security, audit, go, oidc, saml, dependency]
---

# Retest Keamanan MFA Backend

## Ringkasan Eksekutif

- Retest terhadap source code `/home/said/mfa-be` berhasil dijalankan menggunakan Go 1.26.5.
- Seluruh unit test Go berhasil.
- Retest awal menemukan dua kerentanan dependency reachable pada `pgx/v5` dan `goxmldsig`; keduanya telah di-upgrade dalam source pada pembaruan remediation ini.
- Remediasi source diterapkan untuk validasi OIDC, binding authorization code/client, autentikasi token endpoint, cookie session, trust proxy header, metrics, dan fallback OIDC signing secret.
- Retest deployment belum lengkap karena `mfa-be.eguard.id` masih gagal resolusi DNS dari environment pemeriksaan; perubahan source belum membuktikan bahwa deployment live telah diperbarui.

## Tujuan dan Ruang Lingkup

- **Tujuan:** memverifikasi ulang hasil audit keamanan menggunakan toolchain Go yang tersedia.
- **Cakupan:** source code, unit test, dependency vulnerability scan, serta pengecekan pasif terhadap deployment.
- **Di luar cakupan:** brute force, denial-of-service, perubahan data produksi, eksploitasi destruktif, dan pengujian dengan kredensial nyata.

## Hasil / Perubahan

- Go terverifikasi: `go1.26.5 linux/amd64`.
- `go test ./...` selesai dengan status sukses pada seluruh package.
- Retest awal `govulncheck ./...` mengembalikan exit code 3 karena dua vulnerability reachable; setelah upgrade dependency, scan ulang menghasilkan **0 vulnerability yang reachable**.
- Source application diperbarui untuk menghapus hard-coded fallback secret, memaksa OIDC client/redirect URI terdaftar, mengikat authorization code ke client ID, mewajibkan client secret pada token endpoint, serta mengamankan cookie, proxy headers, dan metrics.
- Regression test keamanan ditambahkan pada `cmd/server/security_regression_test.go`; test suite penuh berhasil.
- Report audit teknis diperbarui di `/home/said/mfa-be/security-audit-report.md`.

## Temuan dan Dampak

| Prioritas awal | Temuan | Remediasi source | Status source | Status live |
|---|---|---|---|---|
| High | GO-2026-5004 pada `github.com/jackc/pgx/v5@v5.6.0` | Upgrade `pgx/v5` ke `v5.9.2`; `govulncheck` scan ulang. | **Tertutup** — tidak lagi reachable. | Menunggu deploy/retest |
| High | GO-2026-4753 pada `github.com/russellhaering/goxmldsig@v1.3.0` | Upgrade `goxmldsig` ke `v1.6.0`; `govulncheck` scan ulang. | **Tertutup** — tidak lagi reachable. | Menunggu deploy/retest |
| High | OIDC menerima redirect URI arbitrary dan client tidak terdaftar | Exact-match terhadap redirect URI terdaftar; hanya aplikasi OIDC aktif yang diterima pada authorize/verify/token. | **Tertutup** | Menunggu deploy/retest |
| High | Authorization code tidak di-bind ke `client_id` dan token endpoint tanpa client authentication | Code menyimpan `client_id`; token endpoint memeriksa client ID, redirect URI, dan client secret. | **Tertutup** | Menunggu deploy/retest |
| Medium | Cookie autentikasi tidak menetapkan `Secure` | Semua set/clear cookie session menetapkan `Secure: true`. | **Tertutup** | Menunggu deploy/retest |
| Medium | `X-Forwarded-*` dipercaya tanpa validasi proxy | Forwarded headers hanya digunakan jika remote address masuk `TRUSTED_PROXY_CIDRS`. | **Tertutup** | Menunggu konfigurasi CIDR dan deploy |
| Low | Endpoint `/metrics` publik dan build label `dev` | Wajib `METRICS_BEARER_TOKEN`; build label dihilangkan. | **Tertutup** | Menunggu token/config dan deploy |
| High, conditional | Fallback secret OIDC hard-coded | Tidak ada fallback; issuance gagal bila `OIDC_SIGNING_SECRET` kosong. | **Tertutup** | Menunggu deploy/retest |

## Bukti dan Verifikasi

- `/home/said/.local/opt/go/bin/go version` → `go version go1.26.5 linux/amd64`.
- `/home/said/.local/opt/go/bin/go test ./...` → PASS; seluruh package berhasil.
- Retest awal `/home/said/.local/opt/go/bin/go run golang.org/x/vuln/cmd/govulncheck@latest ./...` → exit code 3; dua vulnerability reachable dilaporkan.
- Setelah remediation, `go test ./...` → PASS; seluruh package berhasil.
- Setelah remediation, `go run golang.org/x/vuln/cmd/govulncheck@latest ./...` → **0 vulnerability reachable**.
- Regression checks → cookie `Secure`, metrics bearer auth, trusted proxy handling, dan fail-closed OIDC signing seluruhnya PASS.
- `curl -skS https://mfa-be.eguard.id/` → gagal dengan `Could not resolve host: mfa-be.eguard.id`.
- Bukti source OIDC: `cmd/server/main.go:1015-1125`.
- Bukti cookie: `cmd/server/main.go:2368-2380`.
- Bukti security header/proxy handling: `cmd/server/main.go:431-443` dan `2451-2480`.
- Bukti metrics: `cmd/server/main.go:268-273` dan `460-480`.

## Risiko, Batasan, dan Asumsi

- Status deployment diberi `partial` karena DNS deployment belum dapat di-resolve; header HTTP, TLS, route exposure, dan konfigurasi runtime belum dapat diverifikasi langsung.
- Dependency yang dilaporkan reachable harus dianggap perlu remediation sampai upgrade dan scan ulang berhasil.
- Nilai secret, token, password, dan data pribadi tidak dicantumkan dalam dokumen ini.
- Severity merupakan prioritas triage berbasis source evidence dan dapat berubah setelah validasi deployment serta konfigurasi reverse proxy.

## Rekomendasi / Tindak Lanjut

- [x] Upgrade `github.com/jackc/pgx/v5` ke `v5.9.2` dan `github.com/russellhaering/goxmldsig` ke `v1.6.0`.
- [x] Jalankan `go mod tidy`, `go test ./...`, lalu `govulncheck ./...`; hasil scan ulang: 0 vulnerability reachable.
- [x] Terapkan allowlist redirect URI exact-match dan tolak OIDC client yang tidak terdaftar.
- [x] Bind authorization code ke client ID dan redirect URI; autentikasi confidential client pada token endpoint.
- [x] Hapus fallback OIDC signing secret dan fail closed jika secret tidak tersedia.
- [x] Tambahkan `Secure: true` pada seluruh cookie session/authentication.
- [x] Batasi `X-Forwarded-Host`, `X-Forwarded-Proto`, dan `X-Forwarded-For` hanya melalui `TRUSTED_PROXY_CIDRS`.
- [x] Batasi endpoint `/metrics` dengan `METRICS_BEARER_TOKEN` dan hilangkan label build `dev`.
- [ ] Konfigurasikan nilai production `METRICS_BEARER_TOKEN` dan `TRUSTED_PROXY_CIDRS`, lalu deploy source yang telah diremediasi.
- [ ] Setelah DNS/deployment diperbaiki, ulangi pemeriksaan pasif terhadap TLS, HTTP redirect, headers, health/readiness, metrics, OpenAPI, dan route unauthenticated.

## Changelog

- 2026-07-20 — Dokumen dibuat dari retest keamanan MFA backend menggunakan Go 1.26.5.
- 2026-07-20 — Ditambahkan hasil `go test`, `govulncheck`, dan batasan resolusi DNS deployment.
- 2026-07-20 — Remediasi source: dependency upgraded, OIDC hardening, client authentication, secure cookies, trusted proxy headers, metrics bearer auth, dan fail-closed signing secret; `govulncheck` ulang tidak menemukan vulnerability reachable.

## Referensi Internal

- Source: `/home/said/mfa-be`
- Report teknis: `/home/said/mfa-be/security-audit-report.md`
- Deployment yang diuji: `https://mfa-be.eguard.id` (belum terverifikasi karena DNS gagal)

Belum dipublikasikan ke URL publik.

---

## Catatan Publikasi

Dokumen ini tidak memuat secret, token, password, payload eksploitasi, atau data pribadi mentah. Detail teknis yang diperlukan untuk remediation dipertahankan tanpa instruksi eksploitasi operasional.
