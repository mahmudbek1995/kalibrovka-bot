# 📐 X, Y, Z O'qlari Kalibrovka Boti va Web-Kalkulyatori

Ushbu dasturiy ta'minot 3D printerlar, CNC stanoklar, lazer apparatlari yoki har qanday chiziqli harakatlanuvchi mexanizmlarni kalibrovka qilish, o'lchovlardagi nomutanosiblik va og'ishlarni tahlil qilish uchun mo'ljallangan.

---

## 🌟 Imkoniyatlari

1. **X, Y, Z O'qlari Tahlili:**
   - Har bir o'q uchun alohida yoki barchasi uchun bir vaqtda hisob-kitob.
   - **Kutilgan o'lcham (Etalon / 100%):** Chiqishi kerak bo'lgan nominal razmer (masalan, 20.00 mm yoki 100.00 mm).
   - **1-natija va 2-natija:** Bir nechta o'lchovlarni kiritish va o'rtacha qiymatni hisoblash.
   - **O'lchovlar farqi va barqarorlik:** O'lchov asbobi va mexanikaning takrorlanuvchanlik holati (aniq/qoniqarli/xatoli).

2. **100% da Chiqqan O'lchamdan Yangi Foizni Hisoblash (Scale %):**
   - Agar 100% da chiqarilgan detal kutilgan razmerda chiqmasa, uni to'g'irlash uchun **necha foizga qo'yish kerakligini** hisoblab beradi.
   - Formulasi:
     $$\text{Yangi foiz } (\%) = \text{Hozirgi foiz } (100\%) \times \left(\frac{L_{\text{kutilgan}}}{M_{\text{o'rtacha}}}\right)$$
   - *Misol:* Kutilgan o'lcham 50 mm, 100% da esa 48.5 mm chiqdi:
     $$\text{Yangi masshtab} = 100\% \times \frac{50}{48.5} = \mathbf{103.09\%} \quad (+3.09\% \text{ ga oshirish kerak})$$

3. **Proporsional qadamlar (Steps/mm) formulasi:**
   $$\text{O'rtacha o'lcham } (M_{o'rtacha}) = \frac{M_1 + M_2}{2}$$
   $$\text{Og'ish } (\Delta) = M_{o'rtacha} - L_{kutilgan}$$
   $$\text{Tuzatish koeffitsiyenti } (K) = \frac{L_{kutilgan}}{M_{o'rtacha}} \times 100\%$$
   $$\text{Yangi qadam (Steps/mm)} = \text{Eski qadam} \times \left(\frac{L_{kutilgan}}{M_{o'rtacha}}\right)$$

4. **3D Vizualizator va G-Code generatori:**
   - O'lchov deformatsiyasini ko'rsatuvchi interaktiv 3D kub.
   - To'g'ridan-to'g'ri nusxalash uchun `M92 X... Y... Z...` va `M500` komandalari.

5. **Tarix va Eksport:**
   - Hisob-kitoblar tarixini saqlash (brauzer xotirasi).
   - Natijalarni **CSV (Excel)** formatida yuklab olish.
   - Telegram WebApp orqali natijalarni ulashish.

---

## 🚀 Ishga tushirish usullari

### 1. Veb-sahifani brauzerda ochish:
- Shunchaki [`index.html`](file:///c:/Users/Predator/Desktop/KALIBROVKA%20BOT/index.html) faylini sichqonchaning chap tugmasi bilan ikki marta bosib brauzerda oching.
- Yoki terminalda quyidagi buyruqni bering:
  ```bash
  python server.py
  ```
  Bu avtomatik tarzda `http://localhost:8080` manzilini brauzeringizda ochadi.

### 2. Telegram Botni ishga tushirish:
1. `bot.py` faylini oching va `BOT_TOKEN` o'rniga [@BotFather](https://t.me/BotFather) dan olgan tokeningizni yozing.
2. Terminalda botni ishga tushiring:
   ```bash
   python bot.py
   ```
3. Botda quyidagi imkoniyatlar bor:
   - `/start` — Interaktiv menyu va barcha tugmalar.
   - `🎯 100% dan Yangi Foizni Hisoblash` tugmasi — Bosqichma-bosqich yangi masshtab foizini hisoblaydi.
   - `/foiz [Kutilgan] [1-natija] [2-natija]` — Yangi kerakli foizni hisoblash:
     Masalan: `/foiz 50 48.4 48.6` yoki `/foiz 100 98.5`
   - `/calc [O'Q] [Kutilgan] [1-natija] [2-natija] [Hozirgi_qadam]` — Qadamlarni (Steps/mm) hisoblash:
     Masalan: `/calc X 20 19.80 19.86 80`
   - **Smart avto-hisoblash:** Botga shunchaki raqamlarni yozib yuborish kifoya (masalan: `50 48.5` yoki `50 48.4 48.6`) — bot o'zi tushunib yangi foizni darhol chiqarib beradi!
