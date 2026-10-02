# SecureChat

Mesajların ve paylaşılan dosyaların şifreli olarak saklandığı, gerçek zamanlı bir mesajlaşma uygulaması.

Django ve Django Channels üzerine kurulu. Mesajlar WebSocket üzerinden anlık iletiliyor; metin içerikleri ve yüklenen dosyalar veritabanında ve diskte okunamaz biçimde tutuluyor.

> 2026 yaz stajı kapsamında, [TechNarts](https://technarts.com) bünyesinde dört hafta içinde geliştirildi.

<!-- EKRAN GÖRÜNTÜLERİ
Aşağıdaki satırları açın ve docs/ klasörüne görüntüleri ekleyin:

![Sohbet ekranı](docs/sohbet.png)
![Grup ayarları ve davet linki](docs/grup.png)
![Dosya paylaşımı](docs/dosya.png)
-->

---

## Neler yapıyor

**Gerçek zamanlı mesajlaşma** — Anlık teslim, okundu bilgisi, yazıyor göstergesi ve çevrimiçi durumu. Hepsi sayfa yenilenmeden.

**Şifreli dosya paylaşımı** — 50 MB'a kadar dosya ve görsel. Dosyalar parça parça şifrelenerek diske yazılıyor, yalnızca sohbetin katılımcıları indirebiliyor.

**Grup yönetimi** — Yönetici sistemi, üye ekleme/çıkarma, kriptografik olarak imzalanmış davet linki ve linki geçersiz kılma.

**Kimlik doğrulama** — E-posta ile kod doğrulama, oturum tabanlı giriş, kaba kuvvet koruması.

**Arkadaşlık sistemi** — Sohbetler yalnızca arkadaş olan kullanıcılar arasında kurulabiliyor.

**Sohbet deneyimi** — Mesaj sabitleme, mesaj silme, görsel önizleme, grup olaylarının sistem bildirimi olarak gösterilmesi, mesaj içindeki linklerin tıklanabilir olması.

---

## Mimari

```
Tarayıcı ──HTTP──┐
                 ├──> Daphne (ASGI) ──┬──> Django        ──> PostgreSQL
Tarayıcı ──WS────┘                    └──> ChatConsumer  ──> Redis (kanal katmanı)
                                                          └──> Disk (şifreli dosyalar)
```

Tek bir sunucu süreci hem HTTP hem WebSocket taşıyor; ayrım ASGI katmanında yapılıyor. Klasik WSGI arayüzü istek-cevap modeline göre tasarlandığından uzun süre açık kalan bağlantıları taşıyamıyor.

Redis burada bir veri deposu değil, **süreçler arası mesaj yolu**. İki kullanıcı farklı sunucu süreçlerine bağlıysa birbirinin belleğini göremez; kanal katmanı bu yüzden var ve yatay ölçeklemeyi mümkün kılıyor.

---

## Teknik derinlik

### İki ayrı şifreleme katmanı

Metin mesajları ve dosyalar farklı kısıtlara sahip olduğu için iki ayrı çözüm kullanılıyor.

**Mesajlar — Fernet.** AES-128-CBC ve HMAC-SHA256 bir arada. Her şifrelemede rastgele bir başlangıç vektörü üretiliyor, bu yüzden aynı metin iki kez şifrelendiğinde farklı çıktı veriyor. Düz metin hiçbir aşamada saklanmıyor.

**Dosyalar — AES-256-GCM, parçalı.** Fernet dosyalar için uygun değil: veriyi bir bütün olarak belleğe alıyor ve base64 kodlaması boyutu %33 büyütüyor. Bunun yerine dosya 64 KB'lık parçalara bölünüp her parça ayrı şifreleniyor — bellek kullanımı dosya boyutundan bağımsız kalıyor.

Ancak parçalı şifreleme, şifreleme işlevini bir döngüye almaktan ibaret değil. Doğrudan gerçeklenen bir parçalı şifreleme üç saldırıya açık:

| Saldırı | Ne oluyor | Savunma |
|---|---|---|
| **Nonce tekrarı** | Aynı anahtar+nonce ikilisi iki kez kullanılırsa GCM'in imza anahtarı sızar | Nonce = 4 bayt rastgele önek + 8 bayt artan sayaç |
| **Parça karıştırma** | Her parça kendi başına geçerli olduğundan sıraları değiştirilebilir | Sayaç zaten nonce'un içinde — yanlış sıradaki parça çözülemiyor |
| **Kırpma** | Son parçalar silinirse kalanlar geçerli doğrulanır, eksilme fark edilmez | Son parça "ben sonuncuyum" bilgisiyle imzalanıyor (AAD) |

Bu yapının adı **STREAM** (Rogaway ve ark.); `age` şifreleme aracı ve Google Tink de aynı yaklaşımı kullanıyor.

**Anahtar yönetimi — zarf şifreleme.** Her dosya için ayrı bir anahtar üretiliyor, dosya onunla şifreleniyor, anahtar da ana anahtarla sarılıp veritabanında saklanıyor. Ana anahtarı değiştirmek gerektiğinde terabaytlarca dosya değil, sadece küçük anahtarlar yeniden şifreleniyor.

Dosya formatı:

```
[4 bayt "SCF1"][4 bayt nonce öneki][parça 0][parça 1]...[son parça]
```

### Davet linki: durumsuzluktan minimum duruma

Grup davet linki Django'nun `signing` modülüyle imzalanıyor. Burada **şifreleme değil imzalama** var: linkin içeriği gizli değil (zaten tıklayan kişi grubu görecek), engellenmek istenen sahte link üretilmesi.

Başlangıçta token tamamen **durumsuz** tasarlanmıştı — veritabanında hiçbir kayıt yok, token kendi imzasıyla doğrulanıyor. Kazancı basitlikti: tablo yok, sorgu yok, temizlik derdi yok.

Bedeli ise **iptal edememekti.** Link sızarsa durduracak bir mekanizma yok, çünkü sunucunun karşılaştıracağı bir kayıt yok.

Her token'ı saklamak çözüm olurdu ama grup ayarları her açıldığında yeni token üretiliyor; hızla çöp birikirdi. Onun yerine **sohbet başına tek bir sürüm numarası** tutuluyor. Token üretilirken o anki sürüm içine gömülüyor, doğrulanırken karşılaştırılıyor. "Yenile" denince sürüm artıyor ve eski linkler bir anda geçersizleşiyor.

İlginç ayrıntı: eski token'ın **imzası hâlâ geçerli**. Reddedilme sebebi kriptografik değil, uygulama seviyesi bir kural — sürüm eşleşmiyor. İki ayrı kontrol katmanı var.

Hâlâ yapılamayan: tek bir linki iptal edip diğerlerini ayakta tutmak. Sürüm artırmak o gruptaki **tüm** linkleri düşürüyor.

### Idempotency

Ağ tekrarı yüzünden aynı mesaj sunucuya iki kez ulaşabiliyor. Python tarafında "var mı diye bak, yoksa oluştur" yazmak yarış durumuna açık — iki eşzamanlı istek de kontrolü geçebilir.

Bunun yerine istemcinin ürettiği bir UUID, veritabanı seviyesindeki benzersizlik kısıtıyla birleştirildi. Kısıt atomik olduğundan eşzamanlı iki istekte bile tek kayıt oluşuyor. Kimliği istemcinin üretmesi şart: sunucu üretseydi tekrar gelen isteği ayırt edemezdi.

Ödeme sistemlerinin kullandığı *idempotency key* deseninin aynısı.

### Diğer tasarım kararları

- **Yetkilendirme sorgunun içinde.** Ayrı bir `if` yerine filtreye konuyor — kontrolü atlamak yapısal olarak mümkün değil.
- **403 değil 404.** "Yasak" demek kaynağın var olduğunu ele verirdi.
- **Dosya türü içerikten belirleniyor**, uzantıdan veya istemcinin bildiriminden değil.
- **Önce kalıcı hâle getir, sonra haber ver.** Redis çökse bile mesaj kaybolmuyor.
- **Kısıt koda değil modele.** "Sohbette tek sabitli mesaj" kuralı `if` ile değil şemayla uygulanıyor; geçersiz durum temsil bile edilemiyor.

---

## Teknoloji yığını

| Katman | Teknoloji |
|---|---|
| Dil / çatı | Python 3.12, Django 6.1 |
| Gerçek zamanlı | Django Channels 4.3, Daphne (ASGI) |
| Veritabanı | PostgreSQL 16 |
| Kanal katmanı | Redis 7 |
| Şifreleme | `cryptography` (Fernet, AES-256-GCM) |
| Arayüz | Django şablonları, Bootstrap 5 (Bootswatch Zephyr) |
| Ortam | Docker Compose |
| Kod kalitesi | black, flake8 |

---

## Kurulum

### Gereksinimler

- Python 3.12
- Docker ve Docker Compose

### Adımlar

```bash
git clone https://github.com/<kullanici-adi>/securechat.git
cd securechat

# Ortam değişkenleri
cp .env.example .env
# .env dosyasını açıp SECRET_KEY ve FERNET_KEY değerlerini üretin

# Sanal ortam ve bağımlılıklar
python3.12 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# PostgreSQL ve Redis
docker compose up -d db redis

# Veritabanı şeması
python manage.py migrate

# Çalıştır
python manage.py runserver
```

Uygulama `http://127.0.0.1:8000` adresinde açılır.

### Anahtar üretme

```bash
# SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`FERNET_KEY` kaybolursa mevcut mesajlar ve dosyalar bir daha açılamaz.

### E-posta doğrulaması

Varsayılan olarak doğrulama kodları terminale yazdırılır. Gerçek e-posta göndermek için `.env` dosyasına Gmail uygulama şifresi girin (iki adımlı doğrulama açık olmalı).

---

## Testler

```bash
python manage.py test
```

20 test var. Üçü doğrudan saldırı senaryosu: parçaların sırası değiştiriliyor, son parça siliniyor ve veride tek bir bit bozuluyor — her üçünde de çözme işleminin hata vermesi bekleniyor.

```python
def test_truncated_file_rejected(self):
    wrapped = self._encrypt(os.urandom(CHUNK_SIZE * 3))
    header, chunks = self._chunks()
    self.path.write_bytes(header + b"".join(chunks[:-1]))   # son parçayı at

    with self.assertRaises(InvalidTag):
        self._decrypt(wrapped)
```

Erişim denetimi de test ediliyor: katılımcı dosyayı indirebiliyor, katılımcı olmayan 404 alıyor, mesaj silinince diskteki şifreli blob da siliniyor.

---

## Bilinen sınırlar

Bunlar fark edilmemiş eksikler değil, bilinçli kapsam kararları ve tespit edilmiş açıklar:

- **Uçtan uca şifreleme yok.** Anahtar sunucuda olduğundan, sunucuyu yöneten kişi mesajları okuyabilir. Gerçek E2E anahtar değişimi, cihaz senkronizasyonu ve anahtar yedekleme gerektirir; ayrıca sunucu tarafı aramayı tamamen imkânsız kılar.
- **Kayıtta işlem atomikliği yok.** Hesap veritabanına yazıldıktan sonra e-posta gönderiliyor; SMTP patlarsa hesap arafta kalıyor (çift yazma problemi). Çözümü `transaction.atomic`.
- **Yükleme sınırı geç uygulanıyor.** 50 MB kontrolü dosya tamamen alındıktan sonra çalışıyor. Gerçek koruma ters vekil sunucuda olmalı (`client_max_body_size`).
- **Kopan WebSocket bağlantısı toparlanmıyor.** Otomatik yeniden bağlanma yok, kullanıcı sayfayı yenilemek zorunda.
- **Mesajlarda arama yapılamıyor.** İçerik şifreli olduğundan veritabanı araması mümkün değil — şifrelemenin doğrudan bedeli.
- **Dosya meta verisi şifresiz.** İçerik gizli ama dosya adı, boyutu ve türü açık.
- **Profil fotoğrafları erişim kontrolsüz.** Sohbet dosyaları ayrı bir klasörde ve erişim denetimli; profil fotoğrafları hâlâ standart medya klasöründe.

## Sıradaki adımlar

- `transaction.atomic` ile kayıt akışının atomik hâle getirilmesi
- WebSocket için üstel geri çekilmeli yeniden bağlanma
- Profil fotoğraflarına erişim denetimi
- Satır içi JavaScript'in statik dosyalara taşınması (CSP başlığı eklenebilmesi için)
- Mesaj listesinde sayfalama ve N+1 sorguların giderilmesi
- Ayarların `base` / `dev` / `prod` olarak ayrılması

---

## Lisans

Bu proje bir staj çalışmasıdır; eğitim amaçlıdır.
