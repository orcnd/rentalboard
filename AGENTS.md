# RentalBoard

FastAPI ve Vue çok kiracılı kiralama ürünü. Varsayılan dev origin `http://127.0.0.1:5174`; hedef Cloudflare Python Workers + D1.

- Para değerleri integer kuruştur. Tarihler gün bazında `[starts_on,ends_on)` şeklindedir; iade günü yeniden kiralanabilir.
- Workspace/rol istemciden alınmaz; session'dan türetilir. Bütün veri sorguları workspace kapsamını korur.
- Rezervasyon çakışması ve aynı ekipmanın iki kişiye fiziksel teslimi SQL guard/index ile atomik engellenir. Yalnız frontend müsaitlik kontrolüne güvenme.
- Üretim demo modu kapalıdır. Demo alanları sentetiktir; testler production üzerinde çalıştırılmaz.
- Test/fixture hazırlığı önce, ardından davranışı koruyan optimizasyon, güvenlik ve sabitlenmiş snapshot'ta validasyon gelir. Kabul kriterini testi geçirmek için gevşetme.
- Factory entegrasyonu `.factory/` içindedir. Tam factory kabul kapısı/model/harici notification veya deploy entegrasyonu tamamlanmış gibi gösterme.
- Mimari/temel tasarım/auth-tenant sınırı değişikliğinde etki analizi ve insan kararı gerekir. Rutin mevcut örüntü uygulamalarını gereksiz onaylara çevirme.
- Yayını kullanıcı yapacak. Yetki verilmeden Cloudflare production/DNS değişikliği yapma; kaynak, test ve deployment dosyalarını hazırla.
