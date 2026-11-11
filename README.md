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

## Kullanım videosu

[RentalBoard kısa kullanım videosunu izle](docs/media/rentalboard-kullanim.webm). Video, yerel ve sentetik demo verisiyle takvimi, ekipman/müşteri yönetimini ve rezervasyon akışını gösterir.

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

## Ücretsiz Cloudflare Tunnel ile yayın

`https://rentalboard.orcuncandan.com` uygulamayı yerelde çalışan FastAPI + SQLite'a bağlayan Cloudflare Tunnel üzerinden sunar. Statik Vue arayüzü Vite preview ile, `/api/*` ise doğrudan Uvicorn ile servis edilir. Cloudflare Workers Free istek başına 10 ms CPU ile sınırlı olduğundan girişte bcrypt işlemi için güvenilir değildir; ücretli Workers CPU limiti bu sebeple kullanılmıyor.

Bu ücretsiz kurulumun çalışması için Windows bilgisayarın, Uvicorn, Vite preview ve `cloudflared` açık kalmalıdır. Bilgisayar uyursa veya kapanırsa site ulaşılamaz. SQLite dosyası `.data/rentalboard-hosted.sqlite` içindedir; düzenli dış yedekleme ve işletim sistemi güncellemeleri gerekir. Cloudflare Tunnel gelen bağlantıyı Cloudflare'dan makineye güvenli tünelden taşır; uygulama ve veriler bu bilgisayarda kalır.

İlk kurulumdan sonra repo klasöründe üç PowerShell terminali aç:

```powershell
# terminal 1 — API ve kalıcı yerel veritabanı
$env:PUBLIC_ORIGIN = 'https://rentalboard.orcuncandan.com'
$env:DEMO_ENABLED = 'false'
$env:ENVIRONMENT = 'production'
$env:RELEASE_ID = 'rentalboard-0.1.0'
$env:DATABASE_PATH = '.data/rentalboard-hosted.sqlite'
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8010 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

```powershell
# terminal 2 — build edilmiş arayüz
npm ci
npm run build
npm run preview
```

```powershell
# terminal 3 — tunnel
cloudflared tunnel --config deploy/self-host/config.yml run rentalboard
```

Windows oturum açıldığında bu üç servisi başlatmak için `powershell -ExecutionPolicy Bypass -File deploy/self-host/register-startup-task.ps1` çalıştır. Task Scheduler kaydı kullanıcı oturumu açılınca API, Vite preview ve tunnel'ı gizli pencerelerde başlatır. Bilgisayar uyursa/kapanırsa internet yayını da durur.

Tunnel ingress kuralı `/api/*` isteklerini `http://127.0.0.1:8010`, diğer istekleri `http://127.0.0.1:4174` hedefine yollar. Örnek şablon `deploy/self-host/tunnel.yml.example` dosyasındadır. Tunnel kimlik bilgilerini repo içine koyma. İlk kayıt ve girişten sonra ikinci bir workspace açarak tenant izolasyonunu elle doğrula. Ücretsiz Workers canary testi sentetik veride kayıt ve rezervasyonu gördü; ayrıca login sırasında gerçek CPU sınırı aşıldı, bu yüzden canary custom domaine bağlanmadı.

## Cloudflare Workers ücretli alternatifi

Eğer bilgisayarın sürekli açık kalması uygun değilse, `wrangler.jsonc` içindeki Workers + D1 yapılandırması kullanılabilir. Bu hesapta deployment sırasında Workers Free, `limits.cpu_ms=30000` değerini reddetti. Free limitini kaldırmak login'de aralıklı 1102/503 üretti; güvenilir kullanım için Workers Paid gerekir. D1 migration'ları `wrangler d1 migrations apply rentalboard --remote` ile tekrar uygulanabilir. Henüz kullanılmayan üretim D1'inde şema/migration kayıtları var, sentetik test verileri temizlendi; self-host SQLite'tan ayrıdır.

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

Bu projede ai-code-factory observer'ı self-host servisin sağlığını ve normalize API 5xx sinyallerini izlemek için çalıştırıldı. Sentetik AI tester akışları kayıt/giriş, ekipman ve müşteri ekleme, rezervasyon oluşturma ve yenileme sonrası kalıcılığı denedi. Bu, fabrikanın tüm kabul becerilerinin, LLM değerlendirmesinin veya otomatik düzeltmenin üretimde etkin olduğu anlamına gelmez; bu adapter'lar bağlı değildir.

Self-host API'yi `EVENT_LOG_PATH=.factory/runs/events.jsonl` ortam değişkeniyle başlat; sonra:

```sh
uv run python scripts/observe.py --factory-root ../ai-code-factory --watch
```

Entegrasyonu sentetik olaylarla tek seferde doğrulamak için API 8008 portunda çalışırken `uv run python scripts/factory_smoke.py --factory-root ../ai-code-factory` çalıştır. Bu kontrol geçici dizin kullanır; gerçek bildirim veya model çağrısı yapmaz.

Observer/worker bağlantısı normalize 5xx/DB sinyallerini ve sağlık kontrolünü kullanır. Mevcut factory sürümünde model beklemede, bildirim yerel inbox'ta, investigation repository context bekleyen intake olarak kalır. Factory kod çalıştırma, harici bildirim, insan onayı ve otomatik deploy tamamlanmış sayılmaz. Sır, parola, cookie veya müşteri metni telemetry'ye yazılmaz.

Güvenlik/kabul incelemesi ve doğrulama sınırları `docs/verification.md` içindedir.
