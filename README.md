# RentalBoard

Fotoğraf/video ekipmanı kiralayan küçük işletmeler için çok kiracılı rezervasyon SaaS MVP'si. FastAPI + Vue 3 + TypeScript; Cloudflare Python Workers ve D1 hedefi.

## Çalışan özellikler

- Hesap oluşturma, bcrypt parola doğrulaması, HttpOnly session ve session'a bağlı CSRF koruması.
- Kullanıcıların ayrı çalışma alanları; server-side owner/operator/viewer yetki kontrolü.
- Haftalık ekipman takvimi, kategori/arama, müşteri ve ekipman ekleme, bakım durumu.
- Veritabanında atomik çakışma kontrolü; aynı ekipmana aynı tarihte paralel rezervasyon yapılamaz.
- Teslim/iade/iptal akışı; önceki iade tamamlanmadan ikinci fiziksel teslim engellenir.
- Günlük ücretler kuruş olarak saklanır, rezervasyon anındaki fiyat korunur. İade tarihi aralığa dahil değildir.
- CSV dışa aktarma; formula injection koruması. Demo verileri sentetiktir ve her demo oturumu ayrı alandadır.
- Normalize operasyon sinyalleri, sağlık endpoint'i ve ai-code-factory observer/worker bağlantısı.

Başlangıç planının 50 ekipman kotası backend/DB seviyesindedir. Ödeme/abonelik tahsilatı yoktur. E-posta doğrulama, parola sıfırlama, ekip daveti/rol yönetimi arayüzü, e-posta bildirimi ve saatlik kiralama bu MVP'ye dahil değildir. API'nin RBAC kuralları test edilir; bu, tamamlanmış ekip yönetimi ürünü değildir.

## Yerel geliştirme

Node 22.12+ ve Python 3.12+ ile:

```sh
npm ci
uv sync
```

İki terminal aç:

```sh
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8008
npm run dev
```

Arayüz: http://127.0.0.1:5174. Yerel varsayılan origin bu adrestir. Demo yerelde açıktır; gerçek hesap boş envanterle başlar. Local SQLite `.data/` altındadır ve Git'e eklenmez. API dokümanı yerel ortamda `/api/docs` yolundadır.

## Cloudflare üzerinde yerel doğrulama

```sh
npm run build
cp .dev.vars.example .dev.vars
npx wrangler d1 migrations apply rentalboard --local
uv run pywrangler dev --port 8790
```

http://127.0.0.1:8790 üzerinde FastAPI, gerçek Workers Python/WASM runtime'ı, local D1 ve derlenmiş Vue birlikte çalışır. `.dev.vars` yalnız yerel ayardır; yayına yüklenmez. Windows'ta `uv` Python indirme/junction sorunu yaşarsa normal bir Python 3.14 kurulumu veya WSL kullan. Projenin yerel API'si 3.12+, doğrulanan Workers runtime'ı 3.14.2'dir.

`pywrangler` uyumlu Pyodide wheel'lerini `python_modules/` içine çözer; bu klasörü Git'e ekleme. `uv.lock` geliştirici bağımlılıklarını sabitler. Workers için oluşturulan `pylock.toml` runtime'a özel üretilir. Paket veya compatibility date değiştiğinde Workers smoke testini yeniden çalıştır.

## rent.orcuncandan.com yayını

Bu repo kendi Cloudflare hesabında yayınlaman için hazırlanmıştır; otomatik deploy yapılmaz.

1. `npx wrangler login` ile kendi hesabına bağlan.
2. `npx wrangler d1 create rentalboard` ile D1 oluştur; dönen ID'yi `wrangler.jsonc` içindeki sıfır ID yerine koy.
3. `PUBLIC_ORIGIN` değerini seçtiğin tam HTTPS adrese ayarla. `DEMO_ENABLED=false` kalsın; production için `ENVIRONMENT=production` ve her release için yeni `RELEASE_ID` kullan.
4. `npx wrangler d1 migrations apply rentalboard --remote` çalıştır. Önce migration/backup planını staging'de doğrula.
5. `npm run build`, ardından `uv run pywrangler deploy` çalıştır.
6. Cloudflare Worker → Settings → Domains & Routes üzerinden `rent.orcuncandan.com` custom domain'ini ekle. Başka subdomain seçersen origin'i de aynı adres yapıp tekrar deploy et.
7. HTTPS origin, kayıt/giriş, CSRF, iki ayrı workspace izolasyonu ve paralel rezervasyonu staging ve gerçek runtime üzerinde doğrula.

Worker ayarı 30 saniye CPU bütçesi içerir; parola hash'leme maliyeti nedeniyle Workers ücretli planı ve kaynak limitleri hesaba katılmalıdır. Paketin ücretsiz planda çalıştığı veya production maliyetinin ölçüldüğü iddia edilmez. Gerçek Cloudflare hesabına deploy ve DNS işlemi bu çalışmada yapılmamıştır.

## Testler

```sh
uv run pytest -q
npm run build
npx playwright install chromium
npm run test:e2e
```

E2E için yerel API ve Vite çalışıyor olmalıdır. `RENTALBOARD_URL=http://127.0.0.1:8790` ile aynı test gerçek local Workers/D1 runtime'ında çalıştırılabilir. Runtime'ı yeniden başlatıp build'i güncel tut. E2E her çalışmada izole sentetik demo alanı oluşturur; production'da çalıştırma.

Gerçek local Workers/D1 üzerinde eşzamanlı API testi: `uv run python -m tests.cloudflare_smoke`. Beş paralel istekte yalnız bir rezervasyon oluşturulmalı, dördü 409 dönmelidir. Bu test localhost dışındaki hedeflerde çalışmaz.

## Fabrika bağlantısı

[ai-code-factory](https://github.com/orcnd/ai-code-factory) reposunu ayrıca klonla. `.factory/acceptance.json` bağımsız iş gereksinimlerini gerçek testlere bağlar. `.factory/known-issues.json` başlangıçta boştur.

API'yi `EVENT_LOG_PATH=.factory/runs/events.jsonl` ortam değişkeniyle başlat; sonra:

```sh
uv run python scripts/observe.py --factory-root ../ai-code-factory --watch
```

Entegrasyonu sentetik olaylarla tek seferde doğrulamak için API 8008 portunda çalışırken `uv run python scripts/factory_smoke.py --factory-root ../ai-code-factory` çalıştır. Bu kontrol geçici dizin kullanır; gerçek bildirim veya model çağrısı yapmaz.

Observer/worker bağlantısı normalize 5xx/DB sinyallerini ve sağlık kontrolünü kullanır. Mevcut factory sürümünde model beklemede, bildirim yerel inbox'ta, investigation repository context bekleyen intake olarak kalır. Factory kod çalıştırma, harici bildirim, insan onayı ve otomatik deploy tamamlanmış sayılmaz. Cloudflare konsol çıktısını bu JSONL akışına taşıyan collector ayrıca yapılandırılmalıdır. Sır, parola, cookie veya müşteri metni telemetry'ye yazılmaz.

Güvenlik/kabul incelemesi ve doğrulama sınırları `docs/verification.md` içindedir.
