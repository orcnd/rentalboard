<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRight,
  CalendarDays,
  Camera,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  Headphones,
  Layers3,
  LayoutGrid,
  LogOut,
  Menu,
  MoreHorizontal,
  Plus,
  Search,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Users,
  Video,
  Wrench,
  X,
  Zap,
} from "@lucide/vue";
import {
  add,
  api,
  day,
  money,
  nights,
  setCsrf,
  type Board,
  type Equipment,
  type Reservation,
  type Session,
} from "./api";

const session = ref<Session | null>(null),
  board = ref<Board>({ equipment: [], customers: [], reservations: [] });
const demoEnabled = ref(false);
const loading = ref(true),
  busy = ref(false),
  error = ref(""),
  notice = ref(""),
  view = ref("calendar"),
  search = ref(""),
  category = ref("all"),
  week = ref(""),
  mobileNav = ref(false);
const authMode = ref("login"),
  auth = reactive({ email: "", password: "", name: "", workspace: "" });
const editingEquipment = ref<Equipment | null>(null);
const dialog = ref<HTMLDialogElement>(),
  modal = ref(""),
  selected = ref<Reservation | null>(null);
const form = reactive({
  equipment_id: "",
  customer_id: "",
  starts_on: "",
  ends_on: "",
  notes: "",
  name: "",
  email: "",
  phone: "",
  category: "camera",
  serial: "",
  day_rate: "",
});
const categories = [
  { id: "all", name: "Tüm ekipmanlar" },
  { id: "camera", name: "Kameralar" },
  { id: "lens", name: "Lensler" },
  { id: "light", name: "Işıklar" },
  { id: "audio", name: "Ses" },
  { id: "accessory", name: "Aksesuarlar" },
];
const statusNames: Record<string, string> = {
  reserved: "Rezerve",
  out: "Kirada",
  returned: "İade edildi",
  cancelled: "İptal edildi",
};
const iconFor = (category: string) =>
  (
    ({
      camera: Camera,
      lens: Camera,
      light: Zap,
      audio: Headphones,
      accessory: Video,
    }) as Record<string, typeof Camera>
  )[category] || Camera;
const today = computed(
  () => session.value?.today || new Date().toISOString().slice(0, 10),
);
const canEdit = computed(() =>
  ["owner", "operator"].includes(session.value?.user.role || ""),
);
const days = computed(() =>
  Array.from({ length: 7 }, (_, i) => add(week.value || today.value, i)),
);
const weekLabel = computed(() => {
  const first = day(days.value[0]!),
    last = day(days.value[6]!);
  return `${first.getUTCDate()}–${last.getUTCDate()} ${new Intl.DateTimeFormat("tr-TR", { month: "long", year: "numeric", timeZone: "UTC" }).format(last)}`;
});
const visibleGear = computed(() =>
  board.value.equipment.filter(
    (e) =>
      (category.value === "all" || e.category === category.value) &&
      `${e.name} ${e.serial}`
        .toLocaleLowerCase("tr")
        .includes(search.value.toLocaleLowerCase("tr")),
  ),
);
const active = computed(() =>
  board.value.reservations.filter((r) =>
    ["reserved", "out"].includes(r.status),
  ),
);
const out = computed(() =>
  board.value.reservations.filter((r) => r.status === "out"),
);
const pickups = computed(() =>
  active.value.filter(
    (r) => r.status === "reserved" && r.starts_on === today.value,
  ),
);
const returns = computed(() =>
  out.value.filter((r) => r.ends_on <= add(today.value, 1)),
);
const filteredReservations = computed(() =>
  [...board.value.reservations]
    .reverse()
    .filter((r) =>
      `${r.customer_name} ${r.equipment_name}`
        .toLocaleLowerCase("tr")
        .includes(search.value.toLocaleLowerCase("tr")),
    ),
);
const filteredCustomers = computed(() =>
  board.value.customers.filter((c) =>
    `${c.name} ${c.email}`
      .toLocaleLowerCase("tr")
      .includes(search.value.toLocaleLowerCase("tr")),
  ),
);
const total = computed(() => {
  const rate =
    board.value.equipment.find((e) => e.id === form.equipment_id)?.day_rate ||
    0;
  return (
    rate *
    Math.max(
      0,
      nights(form.starts_on || today.value, form.ends_on || today.value),
    )
  );
});
const modalTitle = computed(() =>
  editingEquipment.value && modal.value === "equipment"
    ? "Ekipmanı düzenle"
    : (
        {
          reservation: "Yeni rezervasyon",
          equipment: "Ekipman ekle",
          customer: "Müşteri ekle",
          detail: "Rezervasyon detayı",
          guide: "Günün akışı",
        } as Record<string, string>
      )[modal.value] || "",
);
const pageTitle = computed(
  () =>
    (
      ({
        calendar: "Rezervasyon takvimi",
        reservations: "Rezervasyonlar",
        equipment: "Ekipmanlar",
        customers: "Müşteriler",
        settings: "Çalışma alanı",
      }) as Record<string, string>
    )[view.value] || "",
);
function monday(value: string) {
  const date = day(value);
  return add(value, -((date.getUTCDay() + 6) % 7));
}
function shortDate(value: string) {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(day(value));
}
function slots(equipment: Equipment) {
  return active.value.filter(
    (r) =>
      r.equipment_id === equipment.id &&
      r.starts_on < add(week.value, 7) &&
      r.ends_on > week.value,
  );
}
function slotStyle(r: Reservation) {
  const start = Math.max(0, nights(week.value, r.starts_on)),
    end = Math.min(7, nights(week.value, r.ends_on));
  return { gridColumn: `${start + 1} / ${end + 1}` };
}
function changeView(next: string) {
  view.value = next;
  search.value = "";
  mobileNav.value = false;
  error.value = "";
  document.title = pageTitle.value + " · RentalBoard";
}
async function refresh() {
  board.value = await api<Board>("/board");
}
async function load() {
  session.value = await api<Session>("/session");
  setCsrf(session.value.user.csrf);
  if (!week.value) week.value = monday(session.value.today);
  await refresh();
}
async function authenticate(demo = false) {
  busy.value = true;
  error.value = "";
  try {
    const response = await api<{ csrf: string }>(
      demo ? "/auth/demo" : "/auth/" + authMode.value,
      "POST",
      demo
        ? {}
        : authMode.value === "login"
          ? { email: auth.email, password: auth.password }
          : auth,
    );
    setCsrf(response.csrf);
    await load();
    notice.value = demo
      ? "Sana özel demo çalışma alanı açıldı. Değişiklikleri deneyebilirsin."
      : "Çalışma alanın hazır.";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function logout() {
  try {
    await api("/auth/logout", "POST", {});
    session.value = null;
    board.value = { equipment: [], customers: [], reservations: [] };
    setCsrf("");
    week.value = "";
    notice.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  }
}
async function open(
  kind: string,
  equipment?: Equipment,
  reservation?: Reservation,
) {
  modal.value = kind;
  error.value = "";
  selected.value = reservation || null;
  editingEquipment.value = kind === "equipment" && equipment ? equipment : null;
  Object.assign(form, {
    equipment_id: equipment?.id || "",
    customer_id: "",
    starts_on: today.value,
    ends_on: add(today.value, 1),
    notes: "",
    name: "",
    email: "",
    phone: "",
    category: "camera",
    serial: "",
    day_rate: "",
  });
  if (editingEquipment.value)
    Object.assign(form, {
      name: editingEquipment.value.name,
      category: editingEquipment.value.category,
      serial: editingEquipment.value.serial,
      day_rate: String(editingEquipment.value.day_rate / 100),
    });
  await nextTick();
  dialog.value?.showModal();
}
function close() {
  dialog.value?.close();
  modal.value = "";
  error.value = "";
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    if (modal.value === "reservation")
      await api("/reservations", "POST", {
        equipment_id: form.equipment_id,
        customer_id: form.customer_id,
        starts_on: form.starts_on,
        ends_on: form.ends_on,
        notes: form.notes,
      });
    else if (modal.value === "equipment") {
      const amount = Number(String(form.day_rate).replace(",", "."));
      if (!Number.isFinite(amount) || amount < 0 || form.day_rate === "")
        throw Error("Geçerli bir günlük ücret gir.");
      await api(
        editingEquipment.value
          ? "/equipment/" + editingEquipment.value.id
          : "/equipment",
        editingEquipment.value ? "PATCH" : "POST",
        {
          name: form.name,
          category: form.category,
          serial: form.serial,
          day_rate: Math.round(amount * 100),
        },
      );
    } else if (modal.value === "customer")
      await api("/customers", "POST", {
        name: form.name,
        email: form.email,
        phone: form.phone,
      });
    await refresh();
    notice.value = "Kayıt tamamlandı.";
    close();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function transition(status: string) {
  if (!selected.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api("/reservations/" + selected.value.id, "PATCH", { status });
    await refresh();
    notice.value =
      status === "out"
        ? "Ekipman teslim edildi."
        : status === "returned"
          ? "İade kaydedildi."
          : "Rezervasyon iptal edildi.";
    close();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function toggleMaintenance(e: Equipment) {
  busy.value = true;
  try {
    await api("/equipment/" + e.id, "PATCH", {
      state: e.state === "maintenance" ? "available" : "maintenance",
    });
    await refresh();
    notice.value = "Ekipman durumu güncellendi.";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
function exportCsv() {
  const rows = [
    ["Ekipman", "Müşteri", "Başlangıç", "İade", "Durum", "Toplam TRY"],
    ...board.value.reservations.map((r) => [
      r.equipment_name,
      r.customer_name,
      r.starts_on,
      r.ends_on,
      statusNames[r.status] || r.status,
      ((r.day_rate * nights(r.starts_on, r.ends_on)) / 100).toFixed(2),
    ]),
  ];
  const safe = (v: string) =>
    '"' + (/^\s*[=+@\-\t\r]/.test(v) ? "'" + v : v).replaceAll('"', '""') + '"';
  const blob = new Blob(
    ["\ufeff" + rows.map((r) => r.map(safe).join(";")).join("\r\n")],
    { type: "text/csv;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "rentalboard-rezervasyonlar.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
onMounted(async () => {
  try {
    demoEnabled.value = (
      await api<{ demo_enabled: boolean }>("/config")
    ).demo_enabled;
    await load();
  } catch {
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-if="loading" class="loading-screen">
    <span class="brand-mark">r<span>·</span></span>
    <p>Çalışma alanın hazırlanıyor…</p>
  </div>
  <div v-else-if="!session" class="auth-layout">
    <section class="auth-story">
      <a class="wordmark" href="/"
        >rentalboard<span class="brand-dot">.</span></a
      >
      <div class="auth-copy">
        <p class="eyebrow">DAHA AZ TABLO. DAHA NET BİR TAKVİM.</p>
        <h1>Her ekipmanın<br />bir yeri var.</h1>
        <p>
          Rezervasyondan iadeye kadar kiralama işinin bütün akışı, tek bir
          çalışma alanında.
        </p>
        <div class="mini-calendar" aria-hidden="true">
          <div class="mini-head">
            <span>EKİPMAN</span><span>PZT</span><span>SAL</span><span>ÇAR</span
            ><span>PER</span>
          </div>
          <div class="mini-row">
            <Camera :size="24" /><span class="mini-book"
              >Sony A7 IV <small>Mavi Film · 3 gün</small></span
            >
          </div>
          <div class="mini-row">
            <Zap :size="24" /><span class="mini-book second"
              >Çekim ışıkları <small>Studio Kestane</small></span
            >
          </div>
          <div class="mini-foot"><Check :size="15" /> Çakışmalara yer yok.</div>
        </div>
      </div>
      <p class="auth-foot">Ekipmanı kirala. Kontrolü elinde tut.</p>
    </section>
    <section class="auth-form">
      <div class="auth-form-inner">
        <p class="eyebrow">KİRALAMA OPERASYONUNUN ÇALIŞMA ALANI</p>
        <h2>
          {{
            authMode === "register"
              ? "İşine bir alan aç."
              : "Tekrar hoş geldin."
          }}
        </h2>
        <p class="muted">
          {{
            authMode === "register"
              ? "Ekibini ve ekipmanlarını aynı takvimde buluştur."
              : "Takvimin, ekipmanların ve müşterilerin seni bekliyor."
          }}
        </p>
        <form @submit.prevent="authenticate()">
          <template v-if="authMode === 'register'"
            ><label
              >Adın<input
                v-model="auth.name"
                required
                minlength="2"
                autocomplete="name"
                placeholder="Deniz Aksoy" /></label
            ><label
              >İşletme adı<input
                v-model="auth.workspace"
                required
                minlength="2"
                autocomplete="organization"
                placeholder="Kadraja Kiralama" /></label></template
          ><label
            >E-posta<input
              v-model="auth.email"
              type="email"
              required
              autocomplete="email"
              placeholder="sen@isletmen.com" /></label
          ><label
            >Parola<input
              v-model="auth.password"
              type="password"
              required
              minlength="12"
              maxlength="72"
              :autocomplete="
                authMode === 'register' ? 'new-password' : 'current-password'
              "
              placeholder="En az 12 karakter"
          /></label>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <button class="primary full" :disabled="busy">
            {{
              busy
                ? "Hazırlanıyor…"
                : authMode === "register"
                  ? "Çalışma alanını oluştur"
                  : "Giriş yap"
            }}<ArrowRight :size="17" />
          </button>
        </form>
        <p class="auth-switch">
          {{
            authMode === "register"
              ? "Zaten bir hesabın var mı?"
              : "Henüz hesabın yok mu?"
          }}
          <button
            class="text-button"
            @click="
              authMode = authMode === 'register' ? 'login' : 'register';
              error = '';
            "
          >
            {{ authMode === "register" ? "Giriş yap" : "Hesap oluştur" }}
          </button>
        </p>
        <div v-if="demoEnabled" class="divider">
          <span>önce bir göz at</span>
        </div>
        <button
          v-if="demoEnabled"
          class="secondary full"
          :disabled="busy"
          @click="authenticate(true)"
        >
          <Sparkles :size="17" /> Demo çalışma alanını aç
        </button>
        <p v-if="demoEnabled" class="fine-print">
          Demo verileri sentetiktir ve çalışma alanın sana özeldir.<br />Gerçek
          müşteri bilgisi girmen gerekmez.
        </p>
      </div>
    </section>
  </div>
  <div v-else class="shell">
    <a class="skip-link" href="#content">İçeriğe geç</a>
    <aside class="sidebar" :class="{ 'mobile-open': mobileNav }">
      <a class="wordmark" href="/"
        >rentalboard<span class="brand-dot">.</span></a
      >
      <div class="workspace-switch">
        <span class="workspace-avatar">{{
          session.user.workspace_name.charAt(0)
        }}</span>
        <div>
          <strong>{{ session.user.workspace_name }}</strong
          ><span>Kiralama çalışma alanı</span>
        </div>
      </div>
      <p class="nav-label">ÇALIŞMA ALANI</p>
      <nav aria-label="Ana menü">
        <button
          v-for="item in [
            { id: 'calendar', label: 'Takvim', icon: CalendarDays },
            { id: 'reservations', label: 'Rezervasyonlar', icon: Layers3 },
            { id: 'equipment', label: 'Ekipmanlar', icon: Camera },
            { id: 'customers', label: 'Müşteriler', icon: Users },
          ]"
          :key="item.id"
          :class="{ active: view === item.id }"
          :aria-label="item.label"
          :aria-current="view === item.id ? 'page' : undefined"
          @click="changeView(item.id)"
        >
          <component :is="item.icon" :size="19" /><span>{{ item.label }}</span
          ><span v-if="item.id === 'reservations'" class="nav-count">{{
            active.length
          }}</span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <div class="plan-box">
          <div>
            <span class="plan-dot"></span><strong>Başlangıç planı</strong>
          </div>
          <p>
            {{ board.equipment.length }} /
            {{ session.plan.equipment_limit }} ekipman
          </p>
          <div class="usage-track">
            <span
              :style="{
                width:
                  Math.min(
                    100,
                    (board.equipment.length / session.plan.equipment_limit) *
                      100,
                  ) + '%',
              }"
            ></span>
          </div>
          <span class="plan-note">Çalışma alanına dahil</span>
        </div>
        <button class="sidebar-help" @click="open('guide')">
          <CircleHelp :size="18" />Kısa kullanım rehberi<ArrowUpRight
            :size="15"
          /></button
        ><button class="account" @click="changeView('settings')">
          <span class="person-avatar">{{ session.user.name.charAt(0) }}</span
          ><span
            ><strong>{{ session.user.name }}</strong
            ><small>{{
              session.user.role === "owner"
                ? "Çalışma alanı sahibi"
                : session.user.role === "operator"
                  ? "Operatör"
                  : "Görüntüleyici"
            }}</small></span
          ><Settings2 :size="17" />
        </button>
      </div>
    </aside>
    <div class="main-wrap">
      <header class="topbar">
        <div>
          <button
            class="icon-button menu-toggle"
            aria-label="Menüyü aç/kapat"
            @click="mobileNav = !mobileNav"
          >
            <Menu :size="20" /></button
          ><span class="breadcrumb"
            >Çalışma alanı <span>/</span> <strong>{{ pageTitle }}</strong></span
          >
        </div>
        <span class="today-label"
          ><span class="live-dot"></span
          >{{
            new Intl.DateTimeFormat("tr-TR", {
              day: "numeric",
              month: "long",
              year: "numeric",
              timeZone: "UTC",
            }).format(day(today))
          }}</span
        >
      </header>
      <main id="content">
        <div class="page-heading">
          <div>
            <p class="eyebrow">HER ŞEY YERLİ YERİNDE</p>
            <h1>
              {{ pageTitle
              }}<span v-if="view === 'equipment'" class="heading-count">{{
                board.equipment.length
              }}</span>
            </h1>
            <p class="muted">
              {{
                view === "calendar"
                  ? "Kimin neyi, ne zaman kiraladığını tek bakışta gör."
                  : view === "reservations"
                    ? "Yaklaşan teslimleri ve devam eden kiralamaları yönet."
                    : view === "equipment"
                      ? "Envanterini güncel, ekipmanlarını kiralamaya hazır tut."
                      : view === "customers"
                        ? "Bir sonraki kiralama, doğru kişiyle başlar."
                        : "İşletme bilgilerin ve erişim ayarların."
              }}
            </p>
          </div>
          <div class="heading-actions">
            <button
              v-if="view === 'reservations'"
              class="secondary"
              @click="exportCsv"
            >
              <Download :size="16" />CSV indir</button
            ><button
              v-if="view !== 'settings' && canEdit"
              class="primary"
              @click="
                open(
                  view === 'equipment'
                    ? 'equipment'
                    : view === 'customers'
                      ? 'customer'
                      : 'reservation',
                )
              "
            >
              <Plus :size="18" />{{
                view === "equipment"
                  ? "Ekipman ekle"
                  : view === "customers"
                    ? "Müşteri ekle"
                    : "Yeni rezervasyon"
              }}
            </button>
          </div>
        </div>
        <div v-if="notice" class="toast" role="status">
          <Check :size="16" /><span>{{ notice }}</span
          ><button
            class="icon-button"
            aria-label="Bildirimi kapat"
            @click="notice = ''"
          >
            <X :size="15" />
          </button>
        </div>
        <p v-if="error && !modal" class="form-error" role="alert">
          {{ error }}
        </p>
        <template v-if="view === 'calendar'">
          <section class="snapshot" aria-label="Operasyon özeti">
            <div class="snapshot-item">
              <span class="stat-icon"><Camera :size="19" /></span>
              <div>
                <span>Toplam ekipman</span
                ><strong
                  >{{ board.equipment.length }} <small>ekipman</small></strong
                >
              </div>
            </div>
            <div class="snapshot-item">
              <span class="stat-icon sand"><ArrowUpRight :size="19" /></span>
              <div>
                <span>Şu an kirada</span
                ><strong>{{ out.length }} <small>aktif kiralama</small></strong>
              </div>
            </div>
            <div class="snapshot-item">
              <span class="stat-icon blue"><ArrowDownLeft :size="19" /></span>
              <div>
                <span>Yaklaşan iadeler</span
                ><strong
                  >{{ returns.length }} <small>bugün / yarın</small></strong
                >
              </div>
            </div>
            <div class="snapshot-note">
              <span class="small-line"></span>
              <p>İyi bir gün,<br /><strong>net bir takvimle başlar.</strong></p>
            </div>
          </section>
          <section class="calendar-panel" aria-label="Haftalık ekipman takvimi">
            <div class="calendar-toolbar">
              <div class="range-picker">
                <button
                  class="icon-button"
                  aria-label="Önceki hafta"
                  @click="week = add(week, -7)"
                >
                  <ChevronLeft :size="19" />
                </button>
                <h2>{{ weekLabel }}</h2>
                <button
                  class="icon-button"
                  aria-label="Sonraki hafta"
                  @click="week = add(week, 7)"
                >
                  <ChevronRight :size="19" /></button
                ><button class="today-button" @click="week = monday(today)">
                  Bugün
                </button>
              </div>
              <div class="calendar-tools">
                <div class="search-field">
                  <Search :size="16" /><input
                    v-model="search"
                    aria-label="Ekipman ara"
                    placeholder="Ekipman ara…"
                  />
                </div>
                <span class="week-mode"><CalendarDays :size="15" />Hafta</span>
              </div>
            </div>
            <div class="category-tabs" aria-label="Ekipman kategorileri">
              <button
                v-for="c in categories"
                :key="c.id"
                :class="{ selected: category === c.id }"
                :aria-pressed="category === c.id"
                @click="category = c.id"
              >
                {{ c.name
                }}<span v-if="c.id === 'all'">{{
                  board.equipment.length
                }}</span>
              </button>
            </div>
            <div class="calendar-scroll">
              <div class="calendar-table">
                <div class="calendar-header">
                  <div class="equipment-heading">
                    EKİPMAN <span>Günlük ücret</span>
                  </div>
                  <div class="days-header">
                    <div
                      v-for="d in days"
                      :key="d"
                      :class="{
                        today: d === today,
                        weekend: [0, 6].includes(day(d).getUTCDay()),
                      }"
                    >
                      <span>{{
                        new Intl.DateTimeFormat("tr-TR", {
                          weekday: "short",
                          timeZone: "UTC",
                        }).format(day(d))
                      }}</span
                      ><strong>{{ day(d).getUTCDate() }}</strong>
                    </div>
                  </div>
                </div>
                <div
                  v-for="gear in visibleGear"
                  :key="gear.id"
                  class="calendar-row"
                >
                  <button
                    class="equipment-cell"
                    @click="canEdit && open('reservation', gear)"
                  >
                    <span class="gear-avatar" :class="gear.category"
                      ><component
                        :is="iconFor(gear.category)"
                        :size="24"
                        :stroke-width="1.5" /></span
                    ><span
                      ><strong>{{ gear.name }}</strong
                      ><small
                        >{{ money(gear.day_rate) }} <span>/ gün</span></small
                      ></span
                    >
                  </button>
                  <div
                    class="track"
                    :class="{ maintenance: gear.state !== 'available' }"
                  >
                    <div
                      v-for="d in days"
                      :key="d"
                      class="track-day"
                      :class="{
                        today: d === today,
                        weekend: [0, 6].includes(day(d).getUTCDay()),
                      }"
                      @dblclick="
                        canEdit &&
                        gear.state === 'available' &&
                        open('reservation', gear)
                      "
                    ></div>
                    <div
                      v-if="gear.state !== 'available'"
                      class="maintenance-bar"
                    >
                      <Wrench :size="14" />{{
                        gear.state === "maintenance"
                          ? "Bakımda · rezervasyona kapalı"
                          : "Kullanım dışı"
                      }}
                    </div>
                    <button
                      v-for="r in slots(gear)"
                      :key="r.id"
                      class="booking"
                      :class="r.status"
                      :style="slotStyle(r)"
                      :aria-label="`${r.customer_name}, ${gear.name}, ${shortDate(r.starts_on)} – ${shortDate(r.ends_on)}, ${statusNames[r.status]}`"
                      @click="open('detail', undefined, r)"
                    >
                      <span class="booking-mark"></span
                      ><span
                        ><strong>{{ r.customer_name }}</strong
                        ><small
                          >{{ shortDate(r.starts_on) }} –
                          {{ shortDate(r.ends_on) }}</small
                        ></span
                      ><ArrowUpRight v-if="r.status === 'out'" :size="14" />
                    </button>
                  </div>
                </div>
                <div v-if="!visibleGear.length" class="empty-state">
                  <Camera :size="30" />
                  <h3>
                    {{
                      board.equipment.length
                        ? "Eşleşen ekipman yok."
                        : "İlk ekipmanını ekleyelim."
                    }}
                  </h3>
                  <p>
                    {{
                      board.equipment.length
                        ? "Aramayı veya kategori filtresini değiştir."
                        : "Takvim, ekipman eklediğinde burada şekillenecek."
                    }}
                  </p>
                  <button
                    v-if="canEdit && !board.equipment.length"
                    class="secondary"
                    @click="open('equipment')"
                  >
                    Ekipman ekle
                  </button>
                </div>
              </div>
            </div>
            <p class="mobile-calendar-hint">
              Tarihleri görmek için takvimi yana kaydır.
            </p>
            <footer class="calendar-legend">
              <div>
                <span class="legend-dot reserved"></span>Rezerve<span
                  class="legend-dot out"
                ></span
                >Kirada<span class="legend-dot maintenance"></span>Bakımda
              </div>
              <span>İade günü yeni kiralamaya açıktır.</span>
            </footer>
          </section>
          <div class="daily-grid">
            <section class="daily-panel">
              <div class="section-heading">
                <h2>
                  <ArrowUpRight :size="18" />Bugün teslim edilecekler
                  <span>{{ pickups.length }}</span>
                </h2>
                <span class="muted">{{ shortDate(today) }}</span>
              </div>
              <button
                v-for="r in pickups"
                :key="r.id"
                class="daily-item"
                @click="open('detail', undefined, r)"
              >
                <span class="gear-avatar small" :class="r.category"
                  ><component :is="iconFor(r.category)" :size="19" /></span
                ><span
                  ><strong>{{ r.equipment_name }}</strong
                  ><small>{{ r.customer_name }}</small></span
                ><span class="daily-date"
                  >{{ shortDate(r.ends_on) }} iade<ChevronRight :size="16"
                /></span>
              </button>
              <p v-if="!pickups.length" class="quiet-empty">
                <CheckCheck :size="20" />Bugün bekleyen teslim yok. Takvim
                sende.
              </p>
            </section>
            <section class="daily-panel">
              <div class="section-heading">
                <h2>
                  <ArrowDownLeft :size="18" />İadesi yaklaşanlar
                  <span>{{ returns.length }}</span>
                </h2>
                <span class="muted">Bugün / yarın</span>
              </div>
              <button
                v-for="r in returns"
                :key="r.id"
                class="daily-item"
                @click="open('detail', undefined, r)"
              >
                <span class="gear-avatar small" :class="r.category"
                  ><component :is="iconFor(r.category)" :size="19" /></span
                ><span
                  ><strong>{{ r.equipment_name }}</strong
                  ><small>{{ r.customer_name }}</small></span
                ><span class="daily-date"
                  >{{ shortDate(r.ends_on) }}<ChevronRight :size="16"
                /></span>
              </button>
              <p v-if="!returns.length" class="quiet-empty">
                <Clock3 :size="20" />Yaklaşan bir iade bulunmuyor.
              </p>
            </section>
          </div>
        </template>
        <template v-else-if="view === 'reservations'"
          ><div class="list-toolbar">
            <div class="search-field">
              <Search :size="16" /><input
                v-model="search"
                aria-label="Rezervasyon ara"
                placeholder="Müşteri veya ekipman ara…"
              />
            </div>
            <span class="muted"
              >{{ filteredReservations.length }} rezervasyon</span
            >
          </div>
          <div class="data-panel table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Ekipman / müşteri</th>
                  <th>Tarih aralığı</th>
                  <th>Durum</th>
                  <th>Planlanan kira</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in filteredReservations" :key="r.id">
                  <td>
                    <strong>{{ r.equipment_name }}</strong
                    ><small>{{ r.customer_name }}</small>
                  </td>
                  <td>
                    {{ shortDate(r.starts_on) }} – {{ shortDate(r.ends_on)
                    }}<small>{{ nights(r.starts_on, r.ends_on) }} gün</small>
                  </td>
                  <td>
                    <span class="status" :class="r.status">{{
                      statusNames[r.status]
                    }}</span>
                  </td>
                  <td>
                    {{ money(r.day_rate * nights(r.starts_on, r.ends_on)) }}
                  </td>
                  <td>
                    <button
                      class="secondary compact"
                      @click="open('detail', undefined, r)"
                    >
                      Detay
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredReservations.length" class="empty-state">
              <CalendarDays />
              <h3>Henüz bir rezervasyon yok.</h3>
              <p>İlk rezervasyonunu ekleyerek başlayabilirsin.</p>
            </div>
          </div></template
        >
        <template v-else-if="view === 'equipment'"
          ><div class="list-toolbar">
            <div class="search-field">
              <Search :size="16" /><input
                v-model="search"
                aria-label="Envanter ara"
                placeholder="Ekipman veya seri numarası…"
              />
            </div>
            <select v-model="category" aria-label="Kategori">
              <option v-for="c in categories" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </div>
          <div class="inventory-grid">
            <article
              v-for="gear in visibleGear"
              :key="gear.id"
              class="inventory-card"
            >
              <div class="inventory-visual" :class="gear.category">
                <component
                  :is="iconFor(gear.category)"
                  :size="68"
                  :stroke-width="1"
                /><span class="serial">{{
                  gear.serial || "Seri numarası eklenmedi"
                }}</span>
              </div>
              <div class="inventory-body">
                <span class="inventory-category">{{
                  categories.find((c) => c.id === gear.category)?.name
                }}</span>
                <h2>{{ gear.name }}</h2>
                <div class="inventory-price">
                  <strong>{{ money(gear.day_rate) }}<small>/ gün</small></strong
                  ><span
                    class="status"
                    :class="
                      gear.state === 'available' ? 'returned' : 'cancelled'
                    "
                    >{{
                      gear.state === "available"
                        ? "Kullanıma açık"
                        : gear.state === "maintenance"
                          ? "Bakımda"
                          : "Kullanım dışı"
                    }}</span
                  >
                </div>
                <button
                  v-if="canEdit"
                  class="text-button maintenance-action"
                  :aria-label="gear.name + ' düzenle'"
                  @click="open('equipment', gear)"
                >
                  <SlidersHorizontal :size="14" />Düzenle</button
                ><button
                  v-if="canEdit"
                  class="text-button maintenance-action"
                  :disabled="busy"
                  @click="toggleMaintenance(gear)"
                >
                  <Wrench :size="14" />{{
                    gear.state === "maintenance" ? "Bakımı bitir" : "Bakıma al"
                  }}
                </button>
              </div>
            </article>
          </div>
          <div v-if="!visibleGear.length" class="empty-state">
            <Camera />
            <h3>Gösterilecek ekipman yok.</h3>
            <p>Yeni ekipman ekle veya filtreyi değiştir.</p>
          </div></template
        >
        <template v-else-if="view === 'customers'"
          ><div class="list-toolbar">
            <div class="search-field">
              <Search :size="16" /><input
                v-model="search"
                aria-label="Müşteri ara"
                placeholder="Ad veya e-posta ile ara…"
              />
            </div>
            <span class="muted">{{ filteredCustomers.length }} müşteri</span>
          </div>
          <div class="data-panel">
            <div
              v-for="c in filteredCustomers"
              :key="c.id"
              class="customer-row"
            >
              <span class="person-avatar large">{{ c.name.charAt(0) }}</span>
              <div>
                <strong>{{ c.name }}</strong
                ><small
                  >{{ c.email || "E-posta eklenmedi" }}
                  {{ c.phone ? "· " + c.phone : "" }}</small
                >
              </div>
              <span class="muted"
                >{{
                  board.reservations.filter((r) => r.customer_id === c.id)
                    .length
                }}
                rezervasyon</span
              >
            </div>
            <div v-if="!filteredCustomers.length" class="empty-state">
              <Users />
              <h3>Henüz bir müşteri yok.</h3>
              <p>Rezervasyon oluşturmadan önce müşterini ekle.</p>
            </div>
          </div></template
        >
        <section v-else class="settings-panel data-panel">
          <h2>Çalışma alanın</h2>
          <dl>
            <div>
              <dt>İşletme</dt>
              <dd>{{ session.user.workspace_name }}</dd>
            </div>
            <div>
              <dt>Adın</dt>
              <dd>{{ session.user.name }}</dd>
            </div>
            <div>
              <dt>E-posta</dt>
              <dd>
                {{
                  session.user.email.startsWith("demo-")
                    ? "Sana özel demo hesabı"
                    : session.user.email
                }}
              </dd>
            </div>
            <div>
              <dt>Plan</dt>
              <dd>Başlangıç · {{ session.plan.equipment_limit }} ekipman</dd>
            </div>
            <div>
              <dt>Para birimi</dt>
              <dd>Türk lirası (TRY)</dd>
            </div>
          </dl>
          <div class="callout">
            Kiralama tarihleri gün bazındadır. İade tarihi, bir sonraki
            kiralamanın başlayabileceği gündür. Planlanan tutarlar tahsilat veya
            ödeme kaydı değildir.
          </div>
          <button class="secondary" @click="logout">
            <LogOut :size="17" />Oturumu kapat
          </button>
        </section>
        <footer class="app-footer">
          <span>Bir sonraki çekim için hazır.</span
          ><span
            >RentalBoard <span class="brand-dot">·</span> Ekipmanın iş
            başında.</span
          >
        </footer>
      </main>
    </div>
  </div>
  <dialog
    ref="dialog"
    class="modal"
    @close="
      modal = '';
      error = '';
    "
    @click="
      (e) => {
        if (e.target === dialog) close();
      }
    "
  >
    <div class="modal-header">
      <div>
        <p class="eyebrow">RENTALBOARD</p>
        <h2>{{ modalTitle }}</h2>
      </div>
      <button class="icon-button" aria-label="Pencereyi kapat" @click="close">
        <X :size="20" />
      </button>
    </div>
    <form
      v-if="['reservation', 'equipment', 'customer'].includes(modal)"
      class="modal-body"
      @submit.prevent="save"
    >
      <template v-if="modal === 'reservation'"
        ><p class="muted">
          Ekipman, müşteri ve tarihleri seç. Müsaitliği kaydederken kontrol
          edeceğiz.
        </p>
        <label
          >Ekipman<select
            v-model="form.equipment_id"
            aria-label="Ekipman"
            required
          >
            <option value="" disabled>Ekipman seç</option>
            <option
              v-for="e in board.equipment.filter(
                (e) => e.state === 'available',
              )"
              :key="e.id"
              :value="e.id"
            >
              {{ e.name }} · {{ money(e.day_rate) }} / gün
            </option>
          </select></label
        ><label
          >Müşteri<select
            v-model="form.customer_id"
            aria-label="Müşteri"
            required
          >
            <option value="" disabled>Müşteri seç</option>
            <option v-for="c in board.customers" :key="c.id" :value="c.id">
              {{ c.name }}
            </option>
          </select></label
        >
        <p v-if="!board.customers.length" class="muted">
          Önce Müşteriler bölümünden bir müşteri eklemelisin.
        </p>
        <div class="form-columns">
          <label
            >Teslim tarihi<input
              v-model="form.starts_on"
              type="date"
              required /></label
          ><label
            >İade tarihi<input
              v-model="form.ends_on"
              type="date"
              :min="add(form.starts_on || today, 1)"
              required
          /></label>
        </div>
        <p class="field-hint">
          İade günü yeni kiralamaya açıktır. Saatlik kiralama bu sürümde yok.
        </p>
        <label
          >Not <span class="optional">isteğe bağlı</span
          ><textarea
            v-model="form.notes"
            maxlength="1000"
            placeholder="Teslimde dikkat edilecek bir şey var mı?"
          ></textarea>
        </label>
        <div class="quote">
          <span
            >Planlanan kira
            <small
              >{{
                Math.max(0, nights(form.starts_on, form.ends_on))
              }}
              gün</small
            ></span
          ><strong>{{ money(total) }}</strong>
        </div></template
      >
      <template v-else-if="modal === 'equipment'"
        ><label
          >Ekipman adı<input
            v-model="form.name"
            required
            minlength="2"
            maxlength="100"
            placeholder="Sony A7 IV"
        /></label>
        <div class="form-columns">
          <label
            >Kategori<select v-model="form.category" aria-label="Kategori">
              <option
                v-for="c in categories.slice(1)"
                :key="c.id"
                :value="c.id"
              >
                {{ c.name }}
              </option>
            </select></label
          ><label
            >Günlük ücret (₺)<input
              v-model="form.day_rate"
              inputmode="decimal"
              type="number"
              min="0"
              step="0.01"
              required
              placeholder="1850"
          /></label>
        </div>
        <label
          >Seri numarası <span class="optional">isteğe bağlı</span
          ><input
            v-model="form.serial"
            maxlength="80"
            placeholder="SN-0421" /></label
      ></template>
      <template v-else
        ><label
          >Müşteri / işletme adı<input
            v-model="form.name"
            required
            minlength="2"
            maxlength="100"
            placeholder="Mavi Film" /></label
        ><label
          >E-posta <span class="optional">isteğe bağlı</span
          ><input
            v-model="form.email"
            type="email"
            maxlength="200"
            placeholder="iletisim@mavifilm.com" /></label
        ><label
          >Telefon <span class="optional">isteğe bağlı</span
          ><input
            v-model="form.phone"
            type="tel"
            maxlength="30"
            placeholder="05xx xxx xx xx" /></label
      ></template>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="secondary" @click="close">Vazgeç</button
        ><button type="submit" class="primary" :disabled="busy">
          {{
            busy
              ? "Kaydediliyor…"
              : modal === "reservation"
                ? "Rezervasyonu oluştur"
                : "Kaydet"
          }}<Check :size="16" />
        </button>
      </div>
    </form>
    <section v-else-if="modal === 'detail' && selected" class="modal-body">
      <span class="status" :class="selected.status">{{
        statusNames[selected.status]
      }}</span>
      <h3 class="detail-title">{{ selected.equipment_name }}</h3>
      <p class="muted">{{ selected.customer_name }}</p>
      <dl class="detail-grid">
        <div>
          <dt>Teslim tarihi</dt>
          <dd>{{ shortDate(selected.starts_on) }}</dd>
        </div>
        <div>
          <dt>İade tarihi</dt>
          <dd>{{ shortDate(selected.ends_on) }}</dd>
        </div>
        <div>
          <dt>Kiralama süresi</dt>
          <dd>{{ nights(selected.starts_on, selected.ends_on) }} gün</dd>
        </div>
        <div>
          <dt>Planlanan kira</dt>
          <dd>
            {{
              money(
                selected.day_rate *
                  nights(selected.starts_on, selected.ends_on),
              )
            }}
          </dd>
        </div>
      </dl>
      <p v-if="selected.notes" class="detail-note">{{ selected.notes }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div v-if="canEdit" class="modal-actions">
        <button
          v-if="selected.status === 'reserved'"
          class="text-button danger"
          :disabled="busy"
          @click="transition('cancelled')"
        >
          Rezervasyonu iptal et</button
        ><button
          v-if="selected.status === 'reserved'"
          class="primary"
          :disabled="busy || selected.starts_on > today"
          @click="transition('out')"
        >
          <ArrowUpRight :size="16" />Teslim edildi</button
        ><button
          v-if="selected.status === 'out'"
          class="primary"
          :disabled="busy"
          @click="transition('returned')"
        >
          <ArrowDownLeft :size="16" />İadeyi kaydet
        </button>
      </div>
      <p
        v-if="selected.status === 'reserved' && selected.starts_on > today"
        class="field-hint"
      >
        Teslim işlemi başlangıç tarihinde açılır.
      </p>
    </section>
    <section v-else class="modal-body">
      <p>
        Önce ekipmanını ve müşterini ekle, ardından takvimden yeni rezervasyon
        oluştur.
      </p>
      <ol class="guide">
        <li>
          <strong>Tarihleri seç.</strong> İade günü başka bir kiralama
          başlayabilir.
        </li>
        <li>
          <strong>Çakışmayı bize bırak.</strong> Aynı ekipman aynı tarihe ikinci
          kez kaydedilemez.
        </li>
        <li>
          <strong>Teslimi işaretle.</strong> Başlangıç günü rezervasyon
          detayından teslimi kaydet.
        </li>
        <li>
          <strong>İadeyi tamamla.</strong> Ekipman döndüğünde iadeyi kaydet;
          bakım gerekiyorsa envanterden kapat.
        </li>
      </ol>
    </section>
  </dialog>
</template>
