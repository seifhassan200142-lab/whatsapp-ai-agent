# شغّل WhatsApp AI Agent — ابدأ من هنا

المشروع كامل: FastAPI + Groq SDK + WhatsApp Cloud API + SQLite. فيه استقبال رسائل وفويس، ردود من ملف الشركة، ذاكرة، وتحويل لموظف مع لوحة إدارة. مفيش Docker أو LangChain أو vector database أو Google Sheets.

**ابدأ بالترتيب تحت. مش محتاج تذاكر الكود دلوقتي.** الشركة والبيانات الموجودة أمثلة وهمية.

تم اختبار الكود محليًا على Python 3.12.14 / Linux. تشغيل Windows مكتوب لـPython 3.12. الاختبارات بتستخدم Groq SDK الحقيقي وطلبات Meta مع شبكة وهمية. **لم يتم اختبار حساب Meta أو Groq حقيقي أو إرسال واتساب حقيقي أثناء تجهيز النسخة. نجاح الربط النهائي بيتأكد برسالة من موبايلك.** مفيش ضمان إن كل إعدادات حسابات الخدمات الخارجية هتكون جاهزة تلقائيًا.

## 1. تجهيز Windows وVS Code

1. فك ZIP في مكان بسيط، مثل `C:\Projects`، وافتح المجلد `whatsapp-ai-agent` اللي جواه `requirements.txt` و`app`.
2. لو Python مش موجود: نزّل Python 3.12 من [python.org](https://www.python.org/downloads/windows/) واختار Windows installer المناسب، وفعّل **Add python.exe to PATH**. أو افتح PowerShell واكتب:

```powershell
winget install --exact --id Python.Python.3.12
```

3. اقفل التيرمنال وافتحه من جديد بعد التثبيت. افتح VS Code، ثم **File → Open Folder**، واختار مجلد المشروع. لو ظهرت نافذة Workspace Trust للملفات اللي فكيتها، اختار الثقة بعد مراجعتها.
4. من **Terminal → New Terminal** اختار PowerShell. المفروض تكون داخل المجلد اللي فيه `requirements.txt`. نفّذ الأوامر واحد واحد:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m scripts.prepare_env
python -m pytest -q
```

**`Copy-Item` أول مرة فقط. متنسخش `.env.example` فوق مفاتيحك في المرات الجاية.** سكريبت `prepare_env` بيولّد `ADMIN_API_KEY` و`META_VERIFY_TOKEN` عشوائيين، ومش بيغيّر القيم الموجودة بالفعل.

لو التفعيل مرفوض:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

ده للجلسة الحالية فقط. أو استخدم Python بتاع البيئة مباشرة بدون تفعيل:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.prepare_env
```

لو `py` مش معروف و`python --version` بيطلع 3.12، استخدم `python -m venv .venv`. لو الاتنين مش معروفين، أعد فتح VS Code بعد تثبيت Python.

## 2. حط Groq API Key فين؟

من قائمة ملفات VS Code افتح **`.env`**، مش `.env.example`. غيّر أول سطر وحط مفتاحك الحقيقي بعد علامة `=`:

```dotenv
GROQ_API_KEY=PASTE_YOUR_REAL_GROQ_KEY_HERE
GROQ_MODEL=openai/gpt-oss-20b
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
```

استبدل النص `PASTE_YOUR_REAL_GROQ_KEY_HERE` بالكامل. متحطش `Bearer` قبله، ومتبعتهوش في واتساب أو GitHub أو صورة شاشة. باقي المفاتيح هتملاها في الخطوة الجاية.

النموذج الافتراضي `openai/gpt-oss-20b` مستضاف على **Groq**، وكل طلبات الذكاء الاصطناعي رايحة لـGroq. الاسم مش معناه إنك محتاج OpenAI API Key. اخترته من قائمة Groq الحالية، ومتوفر ضمن جدول Free Plan وقت المراجعة. Whisper Turbo بيدعم التفريغ بلغات متعددة.

مش لازم تدفع أو ترقي حسابك للتجربة. راجع [حدود حسابك](https://console.groq.com/settings/limits) واستخدم Free Plan. الكود مبيغيّرش خطة الحساب ولا بيبدّل لخدمة تانية. لو مفتاحك تابع أصلًا لحساب مدفوع، إعدادات فوترة حسابك هي اللي بتطبق.

الإعدادات الافتراضية بتفصل 3 ثواني على الأقل بين بدء طلبات Groq، وبتحط حد محلي 100 استدعاء يوميًا بتوقيت UTC، بما فيها الملخصات والتفريغ والفحوصات. ده احتياط للاختبار، مش ضمان عدم الوصول لحدود التوكنات/الصوت في حسابك. عند 429 مفيش إعادة محاولات تلقائية؛ بيتحفظ سبب العطل وتتوقف المحادثة للمراجعة. بعد إصلاح السبب اضغط تشغيل البوت وابعت رسالة جديدة.

## 3. إعداد Meta ورقم واتساب التجريبي

**تاريخ مراجعة المصادر: 11 أكتوبر 2026.** بعض صفحات Meta الرسمية أعادت 429 أثناء المراجعة؛ لذلك لم أتمكن من فحص كل شاشة الحالية كاملة أو الدخول إلى حسابك. المسارات أدناه تغطي واجهة use cases وواجهة WhatsApp product؛ لو Labels عندك مختلفة، اتبع صفحة [Get Started الرسمية](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) بدل اختيار إعداد عشوائي. وجود الرقم وصلاحياته بيتأكدوا بفحص `--meta` تحت، والويبهوك برسالة فعلية.

### A. اعمل التطبيق ووصل لخانة API Setup

1. افتح [Meta for Developers](https://developers.facebook.com/) وسجّل الدخول بحساب Facebook بتاعك.
2. لو دي أول مرة، أكمل تسجيل حساب المطوّر من **Get Started** أو **My Apps** حسب الصفحة اللي ظهرت لك؛ نفّذ تحقق الهاتف/الإيميل والشروط لو اتطلبوا.
3. افتح [My Apps](https://developers.facebook.com/apps/) واضغط **Create App**.
4. اكتب اسم للتطبيق، مثل `Seif WhatsApp AI Demo`، وإيميل تواصل صحيح.
5. لو ظهرت **Use cases**، اختار حالة استخدام WhatsApp، اللي بتظهر باسم **Connect with customers through WhatsApp** في مسار الإعداد. أكمل **Next** واختار/أنشئ Business Portfolio لو Meta طلبت ده، ثم أكمل إنشاء التطبيق.
6. داخل التطبيق افتح **Use cases → Customize** لحالة WhatsApp؛ الهدف الوصول إلى **API Setup**. في تطبيقات بواجهة المنتجات هتلاقي **WhatsApp → Set up / Quickstart → API Setup**. ولو بتعمل App من واجهة قديمة فيها **Other** ثم نوع التطبيق، اختار **Business** وبعد الإنشاء أضف منتج WhatsApp.
7. أكمل شروط WhatsApp وأي ربط حساب تجريبي تطلبه شاشة الإعداد. في API Setup، اختار حساب WhatsApp التجريبي لو ظهر اختيار الحساب.

**للتجربة المطلوبة استخدم رقم الاختبار اللي Meta بتوفره. متسجلش رقمك الشخصي كرقم إرسال تجاري؛ رقمك الشخصي هنا هو المستلم فقط.** لو الحساب عليه قيد، أو Meta بتطلب تحقق قبل ما تديك أصول الاختبار، لازم تكمل الطلب الظاهر في حسابك؛ الكود مبيقدرش يتجاوز ده.

### B. خد الرقم والـIDs والـToken

داخل **API Setup** ابحث عن جزء إرسال الرسائل:

- **From / Test phone number**: ده رقم واتساب اللي Meta موفّراه. سجّله عندك علشان تبعت له من موبايلك.
- **Phone number ID** أو **Test phone number ID**: انسخ الـID في `META_PHONE_NUMBER_ID`. ده رقم تعريفي، مش رقم الموبايل الظاهر تحت From، ومش App ID أو Messaging account ID/WABA ID.
- **Temporary access token / Generate access token**: ولّد/انسخ توكن الاختبار، واسمح باختيار حساب WhatsApp التجريبي لو ظهرت نافذة تفويض. حط القيمة فقط في `META_ACCESS_TOKEN`.
- **To / Recipient phone number**: افتح اختيار المستلم، ثم **Manage phone number list / Add phone number** لو متاحة. أضف رقم واتساب الشخصي بكود الدولة، وأدخل كود التأكيد بالطريقة اللي Meta تعرضها. مثال: رقم مصري يبدأ `20` أو إماراتي `971`، من غير صفر محلي إضافي بعد كود الدولة.

التوكن المؤقت قصير العمر؛ راجع وقت انتهاء الصلاحية المعروض. لما ينتهي، ولّد واحد جديد وعدّله في `.env` وأعد تشغيل السيرفر. مفيش تجديد تلقائي في المشروع.

### C. هات App Secret وجهّز Verify Token

1. داخل نفس التطبيق افتح **App settings / Settings → Basic**.
2. عند **App secret** اضغط **Show** وأكمل تأكيد حسابك لو اتطلب.
3. انسخ القيمة إلى `META_APP_SECRET`. ده سر التطبيق اللي بيوقّع الـwebhooks؛ **مش Access Token**.
4. `META_VERIFY_TOKEN` موجود بالفعل بعد تشغيل `prepare_env`. دي كلمة عشوائية أنت اخترتها/السكريبت ولّدها، مش بتاخدها من Meta. هتنسخ نفس قيمتها لاحقًا في إعداد الويبهوك.

جدول `.env` النهائي:

| المتغير | تحط فيه إيه؟ |
| --- | --- |
| `GROQ_API_KEY` | مفتاح Groq الموجود معاك |
| `META_ACCESS_TOKEN` | توكن Meta الخاص برقم الاختبار |
| `META_PHONE_NUMBER_ID` | Phone number ID من API Setup |
| `META_APP_SECRET` | App secret من إعدادات نفس التطبيق |
| `META_VERIFY_TOKEN` | القيمة العشوائية اللي جهّزها السكريبت؛ انسخها إلى Meta كما هي |
| `ADMIN_API_KEY` | القيمة العشوائية للوحة الإدارة؛ لا تتحط في Meta |
| `META_GRAPH_VERSION` | الافتراضي `v26.0`؛ قابل للتغيير لإصدار مدعوم من Meta |

`v26.0` ظاهر في المراجع وإصدارات Meta الرسمية الحالية. لو مثال Graph API في API Setup بيستخدم إصدار أحدث، تقدر تنسخه في المتغير وتعيد الفحص. متستخدمش رقم إصدار عشوائي. سكريبت الفحص بيقارن إصدار الاستجابة لو Meta رجّعته.

احفظ الملف بـ **Ctrl + S**، وبعدين:

```powershell
python -m scripts.check_setup
python -m scripts.check_setup --groq --meta
```

المطلوب تشوف `Missing settings: none`، والنموذجين `LISTED`، و`Groq test: OK`، و`Meta token + Phone Number ID: OK`. فحص Groq بيعمل طلب نصي صغير حقيقي؛ فحص Meta قراءة فقط ومبيبعتش واتساب. فحص الصوت الحقيقي لسه في الخطوة 7.

### D. قيود الاختبار

- الإرسال من رقم الاختبار للأرقام اللي اتضافت واتحققت في قائمة المستلمين. التزم بعدد المستلمين والقيود المعروضة في API Setup؛ الحساب التجريبي مش إرسال مفتوح لأي رقم.
- رقم Meta التجريبي مش حساب تقدر تسجّل دخوله في WhatsApp العادي أو WhatsApp Web وتفتحه كصندوق رسائل.
- مشروعنا بيرد نص حر خلال 24 ساعة من آخر رسالة واردة من العميل. لو فاتت، خلي العميل يبعت رسالة جديدة؛ بعد كده شغّل البوت أو رد يدويًا. مفيش إرسال تسويقي أو Templates تلقائية في المشروع.
- رسالة `hello_world` الموجودة في API Setup مفيدة لإثبات إن رقم الاختبار قادر يبعت. **وصولها لوحده مش اختبار للبوت**؛ لازم ترد عليها من موبايلك بعد إعداد الويبهوك.
- رابط `wa.me` في اللوحة بيفتح محادثة من حساب واتساب اللي إنت مسجّل بيه على جهازك. للرد من رقم الاختبار نفسه استخدم خانة الرد اليدوي في لوحة المشروع.
- لا تحتاج استضافة مدفوعة. لو ظهر لك مسار إضافة رقم إنتاج أو فوترة، ارجع لاختيار test number؛ متعتبرش خطوات الإنتاج شرطًا مؤكدًا للتجربة.

## 4. شغّل FastAPI محليًا

في Terminal المشروع، والبيئة مفعّلة:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

**سيب التيرمنال ده شغال.** متستخدمش `--reload` أو أكتر من worker في التجربة دي؛ المشروع عامل معالجة واحدة متسلسلة. إيقافه بـ **Ctrl + C**. بعد أي تعديل `.env` وقّفه وشغّله تاني. تعديل `data/knowledge.md` بيتقرأ مع الرسالة الجديدة من غير restart.

افتح في المتصفح:

- [فحص التشغيل](http://127.0.0.1:8000/health): المفروض `status=ok` و`database=ok` و`configured=true` و`worker_running=true`.
- [Swagger](http://127.0.0.1:8000/docs): هتلاقي API endpoints. زر **Authorize** تدخل فيه قيمة `ADMIN_API_KEY` لو هتجرّب مسارات الإدارة. متحطش `Bearer` قبلها.
- [لوحة الإدارة](http://127.0.0.1:8000/admin): الصق `ADMIN_API_KEY` من `.env` واضغط دخول. الصفحة الأولى نفسها عامة، لكن كل بيانات العملاء والإجراءات ورا فحص المفتاح.

`health` مبيعملش مكالمات خارجية، فنجاحه دليل إن التطبيق شغال فقط. `external_integrations=not_checked_by_health_endpoint` طبيعي. استخدم اللوحة محليًا أثناء التجربة؛ مفيش احتياج تفتحها من ngrok.

## 5. إعداد ngrok وربط الـWebhook

1. اعمل حساب Free من [ngrok](https://dashboard.ngrok.com/signup).
2. افتح [تنزيل ngrok لـWindows](https://ngrok.com/download/windows). تقدر تثبته من Microsoft Store أو تنفّذ الأمر الرسمي:

```powershell
winget install ngrok -s msstore
```

3. افتح Terminal جديد في VS Code بعد التثبيت. انسخ **Authtoken** من لوحة حساب ngrok، واستخدمه بدل النص التالي:

```powershell
ngrok config add-authtoken "PASTE_YOUR_NGROK_AUTHTOKEN"
ngrok http 8000
```

ده **Terminal تاني**؛ الأول لسه مشغّل FastAPI. ngrok token مش Groq key ومش Meta token، ومش مطلوب في `.env`.

4. هتلاقي عنوان HTTPS أمام **Forwarding**. انسخه، مثل `https://your-assigned-domain.ngrok-free.app`. اسم الدومين مثال فقط؛ استخدم اللي ظهر عندك.
5. افتح `https://YOUR_ACTUAL_DOMAIN/health` وتأكد إنه بيوصل للتطبيق. لو المتصفح عرض صفحة تحذير ngrok المجانية، كمل منها مرة عند الاختبار في المتصفح.
6. عنوان الـCallback يكون **نفس عنوان HTTPS زائد `/webhook`**، مثل:

```text
https://YOUR_ACTUAL_DOMAIN/webhook
```

7. في Meta، افتح **WhatsApp → Configuration**، أو داخل **Use cases → Customize → Configuration** حسب واجهة التطبيق.
8. عند إعداد **Webhook** اختار التعديل، والصق الرابط في **Callback URL**.
9. في **Verify token** الصق **قيمة `META_VERIFY_TOKEN`** من `.env`، بدون اسم المتغير وبدون علامات تنصيص.
10. اضغط **Verify and save**. ظهور `webhook_verified` في Terminal FastAPI وحفظ الرابط في Meta معناه إن خطوة GET نجحت.
11. افتح **Webhook fields / Manage** واشترك في **`messages`**. لو شاشة Webhooks العامة بتطلب Object، اختار **WhatsApp Business Account** ثم `messages`. الاشتراك في الحقل ضروري بجانب Verify and save.
12. تأكد إن إعداد WhatsApp مرتبط بالحساب التجريبي الصحيح؛ تغيير التطبيق أو WABA قد يحتاج إعادة إعداد الاشتراك. متختارش webhook لتطبيق Facebook أو Instagram.

الخطة المجانية الحالية بتوفر dev domain معيّن لحسابك؛ مش لازم يتغير كل restart. **قارن العنوان فعليًا كل مرة**. لو اتغير، حدّث Callback URL في Meta وكرر Verify and save؛ مفيش تغيير مطلوب في كود المشروع.

متضيفش صفحة Login أو Basic Auth قدام `/webhook` في ngrok، لأن Meta محتاجة توصله. الحماية هنا بتوقيع Meta. البيانات هتمر عبر ngrok حسب طريقة النفق، وواجهة Traffic Inspector قد تعرض محتوى الطلبات؛ متشاركش سجلها وفيه بيانات عملاء.

## 6. أول تجربة واتساب حقيقية

1. خلي Terminal FastAPI وTerminal ngrok شغالين والكمبيوتر صاحي ومتصل بالإنترنت.
2. اتأكد إن رقمك الشخصي متحقق ومختار ضمن المستلمين في API Setup.
3. من API Setup اختار test number في From، ورقمك في To، وابعت نموذج **hello_world** باستخدام زر إرسال رسالة الاختبار الموجود في الشاشة. لو ماوصلش، أصلح إعداد Meta قبل تجربة البوت.
4. افتح الرسالة على واتساب موبايلك، ورد **من رقمك الشخصي المعتمد إلى رقم اختبار Meta**:

```text
أهلًا، إيه الخدمات اللي بتقدموها؟
```

5. راقب Terminal FastAPI؛ المثال التالي بيوضح أنواع السطور المتوقعة، والأرقام/الأوقات هتختلف:

```text
INFO agent startup_ok missing_settings=none
INFO agent webhook_verified
INFO agent webhook_queued count=1
INFO agent groq_request operation=reply
INFO agent groq_ok operation=reply
INFO agent meta_send_accepted local_id=2
```

6. استنى الرد على موبايلك. `groq_ok` معناه إن طلب Groq رجع، و`meta_send_accepted` معناه Meta قبلت الإرسال؛ **ظهور الرد على واتساب هو تأكيد الوصول**. حالات `delivered/read` تظهر في اللوحة لما إشعار Meta يوصل.
7. افتح لوحة الإدارة واختار **كل المحادثات** ثم **تحديث**. هتشوف رقمك والرسالة والرد.
8. جرّب إنجليزي: `What are your working hours?` المفروض يرد بالإنجليزي بالمعلومة الموجودة في `knowledge.md`.

مفيش طباعة لمفاتيح أو نص المحادثة في logs التطبيق. أمر التشغيل بيوقف access logs علشان رابط تحقق Meta فيه Verify Token. لو هتبعت صورة خطأ، اخفي أي مفاتيح ورقم شخصي.

## 7. تجربة الفويس

1. لو المحادثة حالتها مراجعة بشرية أو مغلقة، اضغط **تشغيل البوت** أولًا.
2. افتح نفس المحادثة على واتساب واضغط الميكروفون وسجّل 5–10 ثواني، مثل: «مواعيد الشغل عندكم إيه؟». ابعت **voice note من واتساب نفسه**.
3. التطبيق يستقبل `messages[].audio.id`، ويستخدم توكن Meta للحصول على رابط تنزيل حديث، وبعد كده ينزّل الملف بالتوكن من مضيف Meta المسموح.
4. فويس واتساب المعتاد OGG/Opus؛ بيتبعت إلى Groq باسم `voice.ogg`. Groq بيدعم OGG مباشرة، **مش محتاج FFmpeg للتجربة دي**.
5. هتشوف `groq_request operation=transcription` ثم `groq_ok operation=transcription` ثم `audio_transcribed`، وبعدهم طلب الرد وإرسال النص إلى WhatsApp.
6. في لوحة الإدارة نوع الرسالة `audio`، وهتلاقي الكلام المفرّغ مكان نص الرسالة. الرد نفسه نص، مش فويس.

أقصى حجم محلي 16,000,000 بايت؛ جرّب رسالة قصيرة لتوفير الحصة. الكود بيدعم OGG وMP3 وM4A وWAV وFLAC وWEBM حسب MIME المسموح، وبيحذف بايتات الصوت من الاستخدام بعد التفريغ بدون ملف صوت دائم. ملفات AAC/AMR منفصلة مش مدعومة في النسخة دي؛ لو ظهر `audio_unsupported_format`، ابعت Voice Note جديدة من التطبيق. مفيش تثبيت FFmpeg أو تحويل تلقائي مطلوب.

## 8. اختبارات الذاكرة والتحويل لموظف

### الذاكرة والحفظ

1. ابعت: `اسمي سيف وعايز موقع لشركة صغيرة`.
2. بعد الرد ابعت: `أنا قلتلك اسمي إيه؟` المفروض يذكر سيف من الرسائل الأخيرة. السياق المرسل للنموذج محدود بآخر 10 رسائل؛ مش كل الأرشيف في كل طلب.
3. افتح اللوحة وشوف الرسائل. قاعدة البيانات هتتعمل تلقائيًا في `data/conversations.sqlite3`، مش مطلوب تثبيت SQLite منفصل.
4. وقّف FastAPI وشغّله تاني، افتح نفس المحادثة؛ البيانات المفروض لسه موجودة. الحالات `human_required` و`resolved` بتفضل زي ما هي بعد restart.

للتأكد من عدد السجلات بدون عرض بيانات خاصة، افتح Terminal ثالث في مجلد المشروع، فعّل البيئة، ونفّذ:

```powershell
python -c "import sqlite3; c=sqlite3.connect('data/conversations.sqlite3'); print('conversations:',c.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]); print('messages:',c.execute('SELECT COUNT(*) FROM messages').fetchone()[0]); c.close()"
```

### سؤال مش موجود في الملف

1. ابعت: `عايز السعر النهائي لموقع كامل وخصم 40% وموافقة على استرداد المبلغ خلال شهر`.
2. مفيش أسعار أو خصومات أو سياسة استرداد مؤكدة في الملف؛ المطلوب يتسجل للمراجعة البشرية، ويجيلك إشعار واحد بإيقاف الردود الآلية.
3. في لوحة الإدارة اختار **محتاجة تدخل بشري** ثم **تحديث**. افتح المحادثة؛ شوف الحالة والملخص ومصدره. `groq` يعني الملخص اتولد بالموديل؛ `fallback` يعني فيه عطل واتحفظ آخر الكلام محليًا بدل ما الطلب يضيع.
4. ابعت `طيب رد عليّ` بعد التحويل؛ هتتحفظ الرسالة، لكن البوت مش هيرد ومش هيكلم Groq. الفويس أثناء التوقف بيتحفظ كـmedia ID فقط، ومش بيتفرغ تلقائيًا.

### طلب موظف صريح ورد يدوي

1. اضغط **تشغيل البوت**، وابعت `عايز أكلم موظف`. ده مسار تحويل مباشر حتى قبل قرار نموذج الرد.
2. افتح اللوحة واكتب ردك في الخانة، مثل: `أهلًا يا سيف، معاك مسؤول الدعم. محتاج أعرف نوع الموقع المطلوب.` واضغط **إرسال الرد**.
3. الرد يتبعت عبر Cloud API من **رقم اختبار Meta نفسه**، خلال نافذة 24 ساعة. المحادثة تفضل `human_required` بعد الرد اليدوي.
4. لما تخلص، اضغط **إغلاق المحادثة** لو عايز توقفها، أو **تشغيل البوت** لو عايز يرجع يرد.
5. بعد تشغيل البوت ابعت **رسالة جديدة**: `إيه مواعيدكم؟`. الرسائل القديمة المتوقفة مش بتتعاد تلقائيًا. الحالة `resolved` كمان مش بتفتح نفسها لو العميل بعت؛ لازم تشغيل البوت يدويًا.

**التحويل هنا معناه تسجيل طلب في لوحة محلية، مش إرسال تنبيه فعلي لموظف أو ضمان إن حد بيراقبها. لازم أنت تفتح اللوحة وتتابعها.**

### API الإدارة لو حبيت تستخدم Swagger

كل المسارات التالية تتطلب هيدر `X-Admin-Key`، والقيمة هي `ADMIN_API_KEY`:

| العملية | المسار |
| --- | --- |
| فحص الإعدادات بدون كشف القيم السرية | `GET /admin/config` |
| قائمة المحادثات | `GET /admin/conversations?status=human_required&limit=100&offset=0` |
| تفاصيل ورسائل | `GET /admin/conversations/{phone}` |
| رسائل أقدم | نفس المسار مع `?before=ID&limit=100` |
| تحويل لموظف | `POST /admin/conversations/{phone}/pause` |
| رجوع البوت | `POST /admin/conversations/{phone}/resume` |
| إغلاق | `POST /admin/conversations/{phone}/resolve` |
| رد يدوي | `POST /admin/conversations/{phone}/reply` مع JSON `{"text":"أهلًا"}` |

استخدم رقم العميل الموجود في اللوحة بدل `{phone}`، بالأرقام الدولية فقط. لو في رد جارٍ حاليًا، إجراء الإدارة بينتظر انتهاءه قبل تغيير الحالة علشان يمنع تعارض الإرسال.

## 9. حل المشاكل — السبب والخطوة المطلوبة

بعد إصلاح مشكلة خدمات خارجية: أعد تشغيل FastAPI لو عدّلت `.env`، افتح المحادثة في اللوحة، اضغط **تشغيل البوت**، وابعت رسالة جديدة. الرسالة الفاشلة مش بتتبعت تلقائيًا مرة تانية.

| المشكلة/الكود | السبب المعتاد | تعمل إيه بالضبط؟ |
| --- | --- | --- |
| `groq_invalid_key` أو 401 | مفتاح Groq غلط/ملغي | افتح `.env`، بدّل `GROQ_API_KEY` بمفتاح صالح من حسابك، احفظ، أعد التشغيل، شغّل `python -m scripts.check_setup --groq` |
| `groq_permission_denied` | حسابك مش مسموح له بالنموذج | راجع Model Permissions وخطة حساب Groq؛ اختار موديل متاح في حسابك ويدعم JSON output، وحدّث `GROQ_MODEL` ثم أعد فحص Groq |
| `groq_model_unavailable` / `groq_bad_request_or_model` | موديل مش متاح أو إعداداته غير مدعومة | ابدأ بالموديل الافتراضي المذكور، وراجع [Models](https://console.groq.com/docs/models). الفحص بيؤكد وجوده ثم يجرب مكالمة فعلية؛ مفيش تغيير موديل تلقائي |
| `groq_rate_limit` / cooldown / 429 | تجاوز حصة الطلبات أو التوكنات أو الصوت | انتظر مدة Retry-After أو تجدد حصتك حسب صفحة Limits؛ قلل الاختبارات والفويس الطويل، ومتضغطش إرسال بشكل متكرر. بعد الانتظار Resume ورسالة جديدة |
| `groq_local_daily_limit` | وصلت 100 مكالمة محلية في اليوم | انتظر يوم UTC جديد؛ لو حصة Groq تسمح فعلًا، عدّل `GROQ_MAX_CALLS_PER_DAY` لقيمة مناسبة ثم أعد التشغيل. متحذفش قاعدة البيانات لتجاوز حدود الخدمة |
| `groq_network_or_timeout` | الإنترنت أو Groq بطيء | افحص اتصالك، جرّب `--groq` مرة واحدة، ولو لزم ارفع `REQUEST_TIMEOUT=60` وأعد التشغيل |
| `groq_invalid_output` | الرد مش JSON صحيح أو خرج عن الشكل المطلوب | البوت وقف المحادثة بدل إرسال جواب غير صالح. اتأكد من موديل يدعم JSON؛ جرّب رسالة قصيرة بعد Resume |
| Meta 401 / code 190 | Access Token غلط أو انتهى | افتح API Setup وولّد temporary token جديد، حطه في `META_ACCESS_TOKEN`، أعد التشغيل ثم `python -m scripts.check_setup --meta` |
| Token سليم بس Meta يرفض الـID | خلط رقم الموبايل بـPhone Number ID أو توكن حساب مختلف | انسخ **Phone number ID** من نفس قسم test number اللي ولّدت له التوكن. متستخدمش App ID أو WABA ID |
| فشل Verify and save | رابط غلط أو السيرفر واقف أو verify token مختلف | افتح public `/health`، شغّل `ngrok http 8000` مع FastAPI، استخدم HTTPS ينتهي `/webhook`، والصق قيمة `META_VERIFY_TOKEN` نفسها بدون مسافات |
| `Invalid webhook signature` / 403 | `META_APP_SECRET` من App تاني، أو طلب يدوي غير موقّع | انسخ App Secret من التطبيق صاحب الـWebhook وأعد التشغيل. متعطلش التحقق. إرسال JSON يدوي من Swagger بدون توقيع متوقع يترفض؛ الاختبارات بتولّد توقيع صحيح |
| رسائل الموبايل مش بتوصل للتطبيق | `messages` مش subscribed أو تطبيق/WABA غلط | راجع Configuration ثم حقل `messages`، وقارن Phone Number ID، وافحص وصول الطلب في ngrok. جرّب رد على hello_world من الرقم المعتمد. اختبارات Meta الوهمية اللي فيها ID مختلف ممكن التطبيق يتجاهلها عمدًا |
| Meta test من الواجهة يوصل لكن رسالة الموبايل لا | قيود حساب/وضع التطبيق أو عدم اشتراك الحساب | راجع تشخيص Webhooks الرسمي وإعداد WhatsApp Business Account. لا تنشر App أو تضف فوترة عشوائيًا؛ نفّذ متطلبات الوضع المعروضة لحسابك. اختبار الهاتف الفعلي هو الفيصل |
| الطلب وصل لكن مفيش رد | المحادثة paused/resolved، أو Groq/Meta فشل | افتح اللوحة ثم **كل المحادثات**؛ راجع `last_error` وحالة آخر رسالة. أصلح السبب ثم تشغيل البوت ورسالة جديدة |
| `meta_delivery_131030` / recipient not allowed | رقم المستلم مش متحقق ضمن قائمة الاختبار | أضف رقم الموبايل إلى To/Manage phone number list في API Setup، أكمل كود التحقق، وابعت منه إلى رقم Meta |
| `meta_delivery_131026` | تعذر التسليم لرقم واتساب/حساب غير متاح | تأكد إن الرقم الصحيح مستخدم على WhatsApp وموافق عليه للاختبار، وإن hello_world بتوصل؛ راجع صفحة أخطاء Meta لو استمر |
| `whatsapp_24h_window_closed` / Meta 131047 | آخر رسالة واردة قديمة | ابعت من موبايل العميل رسالة جديدة، ثم Resume وابعت رسالة أخرى للبوت، أو رد يدويًا بعد الرسالة الجديدة |
| `meta_send_uncertain` أو رسالة `uncertain` | الاتصال اتقطع ومش مؤكد Meta قبلت الإرسال ولا لا | شوف واتساب نفسه قبل أي إعادة إرسال، وبعدها قرر رد يدوي أو Resume. المشروع مبيكررهاش تلقائيًا |
| `restart_interrupted` | السيرفر اتوقف أثناء المعالجة/الإرسال | راجع آخر محادثة على واتساب واللوحة؛ الرد ممكن يكون وصل. بعد المراجعة Resume وابعت رسالة جديدة |
| `audio_download_network` أو Meta 401 عند الصوت | انقطاع اتصال أو توكن منتهي | أصلح الشبكة/جدّد توكن Meta، أعد التشغيل، Resume وابعت فويس جديدة؛ البرنامج بيطلب رابطًا حديثًا لكل ملف |
| `audio_untrusted_url` | رابط وسائط مش من المضيفات المسموحة | راجع الـpayload وإعداد Meta. متضفش دومينات عشوائية وما تبعتش التوكن لرابط عميل؛ جرّب فويس WhatsApp جديدة بعد التأكد |
| `audio_checksum_failed` | الملف المنزّل مش مطابق لبصمته | ابعت فويس جديدة بعد فحص الاتصال. متتجاهلش اختلاف البصمة |
| `audio_too_large` / `audio_transcript_too_long` | ملف أكبر من الحد أو تسجيل طويل | ابعت تسجيل 5–10 ثواني بدل ملف كبير. الحد المحلي 16MB والنص المفرّغ حتى 4096 حرف |
| `audio_unsupported_format` | ملف AAC/AMR أو MIME غير مدعوم | سجّل فويس من ميكروفون WhatsApp نفسه، أو ابعت نص؛ OGG المعتاد مدعوم ومش محتاج FFmpeg |
| تفريغ فاضي أو كلام غلط | صوت منخفض/ضوضاء/تسجيل غير واضح | جرّب فويس قصيرة وواضحة بدون موسيقى؛ لو الحالة اتوقفت اضغط Resume. تقدر تغيّر `GROQ_WHISPER_MODEL=whisper-large-v3` لو متاح في حسابك وتعيد التشغيل |
| ngrok 502 / tunnel offline | FastAPI واقف أو بورت مختلف | تأكد `/health` المحلي شغال، شغّل السيرفر على 8000 ثم `ngrok http 8000`، واستخدم الرابط الحالي |
| ngrok authentication / limit error | authtoken غلط أو حصة الخطة انتهت | أعد `ngrok config add-authtoken` بتوكن حسابك، راجع limits، وأوقف الأنفاق الزائدة. مش مطلوب ترقية تلقائية |
| `No module named ...` أو dependency conflict | التيرمنال بيستخدم Python خارج البيئة | فعّل `.venv` أو استخدم `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` ثم `python -m pip check` |
| PowerShell scripts disabled | سياسة التفعيل | استخدم أمر Set-ExecutionPolicy لجلسة Process الموضح فوق أو شغّل Python البيئة مباشرة |
| `unable to open database file` / init failed | مجلد غير قابل للكتابة أو DB_PATH غلط | حط المشروع في مجلد تملكه مثل Documents، استخدم `DB_PATH=data/conversations.sqlite3`، اتأكد إن `data` موجود وغير read-only، ثم أعد التشغيل |
| `database is locked` | أكتر من نسخة سيرفر/برنامج ماسك قاعدة البيانات | اقفل النسخة الزائدة وبرامج تحرير SQLite، وشغّل Uvicorn مرة واحدة بدون reload/workers إضافيين |
| `knowledge_file_unavailable` | الملف اتنقل/اتحذف | رجّع `data/knowledge.md` أو صحح `KNOWLEDGE_PATH`، واحفظ UTF-8 |
| `knowledge_empty_or_too_large` | الملف فارغ أو أكثر من 14000 حرف | استخدم معلومات الشركة الأساسية فقط؛ حجم صغير مناسب لحصة Groq المجانية |
| الدخول للوحة يرجع 401 | Admin key غلط | انسخ قيمة `ADMIN_API_KEY` من `.env` فقط؛ مش Meta token. لو غيرته أعد تشغيل السيرفر |
| port 8000 already in use | سيرفر قديم لسه شغال | ارجع لتيرمناله واضغط Ctrl+C. متشغّلش نسختين على نفس قاعدة البيانات |

لو حصل تعارض حزم ومش اتحل بالتثبيت، اقفل السيرفر، وافتح Terminal جديد في مجلد المشروع واعمل بيئة جديدة باسم مختلف بدون حذف ملفاتك:

```powershell
py -3.12 -m venv .venv-clean
.\.venv-clean\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
```

## 10. الملفات والتأكد النهائي

| الملف/المجلد | اللي هتستخدمه دلوقتي |
| --- | --- |
| `START_HERE.html` | نفس دليل التشغيل بتنسيق عربي؛ افتحه بدبل كليك في المتصفح |
| `.env.example` | نموذج إعدادات بدون أسرار |
| `.env` | يتعمل على جهازك فقط؛ مش موجود في ZIP |
| `requirements.txt` | الحزم المثبّتة بإصدارات محددة |
| `app/main.py` | مدخل السيرفر والـwebhooks والإدارة |
| `app/config.py` | قراءة الإعدادات |
| `app/whatsapp.py` | إرسال Meta وتنزيل الصوت وفحص التوقيع |
| `app/llm.py` و`app/transcription.py` | Groq للرد والتفريغ |
| `app/database.py` و`app/models.py` | SQLite والتحقق من المدخلات |
| `app/handoff.py` و`app/worker.py` | التحويل ومعالجة الرسائل المسجلة |
| `app/static/` | لوحة الإدارة بدون React أو build step |
| `data/knowledge.md` | عدّل معلومات الشركة هنا |
| `scripts/prepare_env.py` | تجهيز أسرار التحقق والإدارة محليًا |
| `scripts/check_setup.py` | تشخيص الإعدادات والاتصالات الاختياري |
| `tests/` | اختبارات محلية بدون مفاتيح حقيقية |
| `VALIDATION.md` | تقرير الفحوصات وحدود الاختبار |

الرسائل المقبولة بتتحفظ في SQLite قبل رجوع webhook بنجاح، وبعدها المعالجة تحصل في الخلفية. الرسالة بنفس WhatsApp ID مش بتتنفذ مرتين. بعد توقف مفاجئ: الرسائل اللي لسه queued بتكمل، واللي كانت قيد المعالجة بتروح مراجعة بشرية. منع تكرار حدث وارد مش ضمان تسليم شبكة exactly-once؛ لهذا الإرسال غير المؤكد بيتوقف للمراجعة.

الحوار والبيانات محفوظين بدون تشفير على جهازك داخل SQLite، فاحمِ جهازك وما ترفعش قاعدة البيانات. الـZIP مفيهوش أسرار أو محادثات. ملف `.gitignore` بيستبعدهم. مفيش حذف تلقائي للبيانات ولا تشغيل إنتاج متعدد المستخدمين في النسخة دي.

قرار التحويل للنموذج مبني على التعليمات ووجود اقتباس داعم من المعرفة، مع تحقق من شكل الرد؛ ده تقليل للتخمين، مش ضمان إن نموذج لغوي عمره ما يغلط. قبل أي استخدام مع عملاء فعليين جرّب أسئلة شركتك بالعربي والإنجليزي، خصوصًا الأسعار والسياسات.

### المصادر الرسمية

المراجع التالية للتحقق من الإعدادات والخدمات؛ مش مطلوب تقرأها كلها علشان تبدأ:

- [Groq: Models](https://console.groq.com/docs/models) و[GPT-OSS 20B](https://console.groq.com/docs/model/openai/gpt-oss-20b).
- [Groq: Rate limits](https://console.groq.com/docs/rate-limits) و[Speech to text](https://console.groq.com/docs/speech-to-text).
- [Groq Python SDK الرسمي](https://github.com/groq/groq-python).
- [Meta: WhatsApp Get Started](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started) و[Access tokens](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens).
- [Meta: Webhooks](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview) و[Create webhook endpoint](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint).
- [Meta: App settings](https://developers.facebook.com/docs/apps/settings/basic/) و[Graph API versions](https://developers.facebook.com/docs/graph-api/changelog/versions/).
- [Meta Official SDK v26 release](https://github.com/facebook/facebook-python-business-sdk/releases/tag/26.0.0) و[مجموعة WhatsApp الرسمية على Postman](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api).
- [Meta: Error codes](https://developers.facebook.com/documentation/business-messaging/whatsapp/support/error-codes).
- [ngrok: Windows installation](https://ngrok.com/download/windows) و[Free dev domains](https://ngrok.com/blog/free-static-domains-ngrok-users).
