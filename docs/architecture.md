# Ürün ve mimari kararları

İlk kapsam fotoğraf/video ekipmanı kiralayan küçük işletmedir. Türkçe arayüz, TRY ve günlük kiralama kullanılır. Backend FastAPI, frontend Vue 3/TypeScript/Vite; tek origin altında `/api` ayrımı vardır.

## Ortamlar

- Yerel hızlı geliştirme: CPython + Uvicorn + SQLite; frontend Vite proxy.
- Cloudflare: Python Workers/Pyodide ASGI + D1 + Workers Static Assets. Bu ayrı runtime'da da gerçek akış ve paralel çakışma doğrulanır.
- Factory operatörü: RentalBoard'dan ayrı Python observer/worker süreci. Ürünün kaynak kodunu veya prod verisini otomatik değiştiremez. Cloudflare log export collector'ı ayrıca gerekir.

## Veri sınırı

Her kullanıcı bir workspace'e bağlıdır; kayıtlı workspace ID/rolü session join'inden gelir. İstemci workspace/rol seçemez. Ekipman ve müşteri anahtarları reservation FK'sında workspace ile birlikte doğrulanır. Session token'ı hash olarak saklanır; parola bcrypt cost 12 ile hash'lenir, 72 byte üstü reddedilir. Parola ve session token'ı loglanmaz.

## Çakışma ve ücret

Tarih aralığı `[başlangıç,iade)` şeklindedir. Aktif reserved/out kayıtlar için çakışma kontrolü DB trigger'ında atomiktir. UPDATE guard ve tek aktif fiziksel teslim index'i, gecikmiş iadede ikinci müşteriye teslimi önler. Uygulama önce bilgi okusa da DB guard yarış koşuluna karşı son otoritedir.

Günlük ücret integer kuruştur. Yeni rezervasyona ekipmanın o anki fiyatı kopyalanır; sonraki fiyat değişikliği eski teklifleri değiştirmez. Teklif, ödeme/tahsilat kaydı değildir; gecikme bedeli/vergi/fatura hesabı bu kapsamda yoktur.

## Durumlar

`reserved → out → returned`; `reserved → cancelled`. Başlangıçtan önce fiziksel teslim yapılmaz. Update eski durumu WHERE koşulunda karşılaştırır. Başarılı tek health kontrolü factory incident'ini kapatmaz; sağlık ve deploy doğrulaması ayrı katmanlardır.

## İnsan kararı gerektiren kapsam değişiklikleri

Saatlik veya farklı saat dilimlerinde kiralama, çoklu şube/depo, çok sayıda aynı model ekipmanı tek stok satırında toplama, müşteri teminatı/ödeme, otomatik fiyatlandırma ve harici auth sağlayıcısı yeni etki analizi gerektirir. Bunlar mevcut günlük/tekil fiziksel ekipman modelinin sessiz uzantısı olarak uygulanmamalı. Mevcut MVP scope'u için yeni onay veya yapılmamış insan kararı uydurulmaz.
