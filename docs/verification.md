# Doğrulama kaydı

Bu kayıt 9 Kasım 2026 tarihli MVP'nin gerçekten çalıştırılmış kontrollerini ve sınırlarını açıklar. Tam factory kabul gate'i veya üretim onayı değildir.

## Davranışı koruyan optimizasyon

- Yerel SQLite ve Cloudflare D1 aynı query/batch sınırını ve SQL guard'larını kullanır; iş kuralları frontend'e veya bağlantı adaptörlerine kopyalanmaz.
- Takvim tek board isteğiyle yüklenir; her ekipman için ayrı ağ isteği yapılmaz.
- Ücret/tarih iş kuralları merkezi model ve SQL seviyesindedir; UI tahmini otorite değildir.
- Vue/font dosyaları Workers Static Assets üzerinden doğrudan sunulur; Python yalnız `/api` yollarında çalışır.
- Fontlar self-host edilir. Frontend production JS çıktısı yaklaşık 42 KB gzip'tir; bu bir yük/performans benchmark'ı değildir.

## Güvenlik kontrolleri

- Bandit: backend üzerinde 0 bulgu. SAST, mantıksal veya tam güvenlik denetimi yerine geçmez.
- `npm audit --omit=dev`: test anında production paketlerinde bildirilen 0 açık. Python/WASM bağımlılıkları için kapsamlı zafiyet sertifikasyonu yapılmadı.
- Gerçek API testleri: Origin/CSRF, workspace izolasyonu, viewer yazma reddi, yabancı ekipman/müşteri erişimi, durum geçişleri, bakım ve gecikmiş iade kuralı.
- Parola/session/body veya müşteri metni telemetry'ye yazılmaz; arızalı DB simülasyonuyla redakte event akışı test edilir.
- HttpOnly cookie, session bağlı CSRF, güvenli SQL bind'leri, DB FK/guard/index, public/demo ayrımı, CSP/çerçeve engelleme başlıkları.
- Gerçek banka/ödeme, canlı müşteri, production hesabı veya müşteri verisi üzerinde test yapılmadı.

## Çalıştırılmış validasyon

| Kontrol | Gözlenen sonuç |
|---|---|
| `pytest -q` | 14 API/iş kuralı testi geçti |
| `npm run build` | Vue TypeScript kontrolü ve Vite production build geçti |
| Local Vue/FastAPI tarayıcı akışı | Demo, ekipman/müşteri oluşturma, fiyat, rezervasyon, çakışma, iptal, reload, mobil ve logout geçti |
| Aynı E2E, Python Workers + local D1 | Gerçek Pyodide/ASGI runtime ve derlenmiş Vue ile geçti |
| Local Workers'ta 5 paralel rezervasyon isteği | 1 adet 201, 4 adet 409; tek rezervasyon oluştu |
| Factory smoke | Gerçek upstream observer/worker sentetik RentalBoard event'lerini tüketti; gerçek read-only health probe, tek intake ve model bekleme durumu doğrulandı |

## Görsel ve etkileşim doğrulaması

1512 px desktop, 390 ve 320 px dar ekranlarda browser kontrolü yapıldı. Global yatay taşma yok; iki boyutlu takvim kendi alanında yatay kayar. Native dialog, form etiketleri, klavye odak erişimi ve reduced-motion tercihiyle smoke kontrolü yapıldı. Ekran okuyucu veya kapsamlı WCAG uygunluk denetimi yapılmadı. Screenshot'lar `.factory/runs/browser/` altında sentetik veri içerir.

## Hedef runtime

Yerel CPython 3.12.2; gerçek local Workers/Pyodide 3.14.2; Node 22.23.4; Wrangler 4.159.0. Python Workers'ın native extension paketleri farklıdır: bcrypt 4.2.0 wheel'i hedefte bulunmadığı için desteklenen 5.0.0 kullanıldı ve actual runtime'da giriş/demo hash yolu çalıştırıldı. D1 sorguları Workers SDK'sının tipli `.results` çıktısını kullanır; JS stringify üzerinden boş sonuç üretme hatası runtime testiyle giderildi.

## Açık sınırlar

- Cloudflare hesabına production deploy, DNS ve production D1 yapılmadı. D1 ID alanı kullanıcı tarafından doldurulacak placeholder'dır.
- CI workflow eklendi; GitHub sunucusundaki koşu sonucu bu yerel kayıtta doğrulanmış sayılmaz.
- Ücretli abonelik/ödeme, e-posta doğrulama/reset, ekip daveti/rol yönetimi UI'si ve saatlik/çoklu depo kiralaması yok.
- Auth/session kayıtları için retention job'u ve production abuse/Turnstile politikası sonraki işletim işidir.
- Factory'nin LLM logical-evaluation ve kalibrasyon servisleri yapılandırılmadı. Buradaki geçerli testler tam fabrikanın sekiz skill'inin tamamının geçtiği anlamına gelmez.
- Bildirim yerel inbox, investigation yerel intake'tir. Gerçek dış bildirim/model/factory kod çalıştırma ve otomatik deploy yoktur.

## Ücretsiz yayın ve sentetik tester senaryoları (10 Kasım 2026)

- Workers Free canary'de sağlık, kayıt, envanter ve rezervasyon denendi. Bir login isteği Cloudflare `Exceeded CPU Limit` / 1102 ile kesildi; sonraki login denemeleri geçse de bu aralıklı davranış nedeniyle canary silindi ve custom domaine bağlanmadı. Canlı D1 canary satırları temizlendi.
- `rentalboard.orcuncandan.com` Cloudflare Tunnel ile yerel CPython FastAPI + SQLite'a bağlandı; bu, ücretli Workers planı gerektirmeyen self-host yöntemidir. İki bağımsız sentetik tester kaydoldu, giriş/oturum yenilemeyi, ekipman/müşteri eklemeyi, 2 gecelik 2.500 TL rezervasyonu ve sayfa yenileme sonrası kalıcılığı denedi. İki akış da geçti; JavaScript uygulama hatası görülmedi.
- Test hesapları ve rezervasyonlar self-host SQLite'tan temizlendi. Üretim D1'inde migration şeması duruyor, sentetik satırlar yok.
- Statik CSP data font kaynağına izin verecek şekilde düzeltildi. Cloudflare Insights üçüncü taraf betiği CSP tarafından bloklanıyor; analitik devre dışı, RentalBoard akışını etkilemedi.
- Self-host kullanılabilirliği bilgisayarın açık, uyanık ve ağa bağlı olmasına bağlıdır. Windows oturum açma görevi API, arayüz ve tunnel'ı yeniden başlatır; yüksek erişilebilirlik veya sürekli internet bağlantısı garantisi değildir.
- Host makinesinde DNS cache henüz eski NXDOMAIN yanıtı verebildi; Cloudflare authoritative DNS `rentalboard.orcuncandan.com` için proxied A yanıtı veriyor. Bazı DNS resolver'ları negatif önbellek süresi dolana dek gecikebilir.
