import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Bookmark,
  BriefcaseBusiness,
  Building2,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileText,
  Globe,
  HelpCircle,
  LayoutDashboard,
  LoaderCircle,
  MessageCircle,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  Upload,
  X,
  Zap,
  AlertCircle,
  SlidersHorizontal,
  Menu,
} from "lucide-react";
import { api, post, openPdf } from "./api";
import "./style.css";

type Dict = Record<string, any>;
const roles: Dict = {
  cfo: "Финансовый директор",
  ceo: "Генеральный директор",
  treasurer: "Казначей",
};
const topicNames: Dict = {
  rates: "Финансирование",
  demand: "Потребление",
  trade: "Внешняя торговля",
  industry: "Промышленность",
  regulation: "Регулирование",
  economy: "Экономика",
};
const topicIcons: Dict = {
  rates: TrendingUp,
  demand: BarChart3,
  trade: Globe,
  industry: Building2,
  regulation: ShieldCheck,
  economy: Activity,
};
const money = (n: number | null) =>
  n == null
    ? "Не указана"
    : new Intl.NumberFormat("ru-RU", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(n);
const date = (s: string) =>
  s
    ? new Date(s).toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "short",
      })
    : "Дата не указана";
function Spinner() {
  return <LoaderCircle className="spin" size={19} />;
}
function Tag({
  children,
  tone = "grey",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"tag " + tone}>{children}</span>;
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Search size={30} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

function App() {
  const [status, setStatus] = useState<Dict | null>(null),
    [companies, setCompanies] = useState<Dict[]>([]),
    [company, setCompany] = useState(""),
    [role, setRole] = useState("cfo");
  const [page, setPage] = useState("feed"),
    [topic, setTopic] = useState(""),
    [events, setEvents] = useState<Dict[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [selected, setSelected] = useState<Dict | null>(null),
    [result, setResult] = useState<Dict | null>(null),
    [busy, setBusy] = useState(false),
    [detailTab, setDetailTab] = useState("analysis");
  const [docs, setDocs] = useState<Dict[]>([]),
    [metrics, setMetrics] = useState<Dict | null>(null),
    [profile, setProfile] = useState<Dict | null>(null),
    [modal, setModal] = useState("");
  const [toast, setToast] = useState(""),
    [auth, setAuth] = useState(false),
    [authCode, setAuthCode] = useState(""),
    [search, setSearch] = useState(""),
    [mobile, setMobile] = useState(false);
  const [refreshing, setRefreshing] = useState(false),
    [question, setQuestion] = useState(""),
    [chat, setChat] = useState<Dict[]>([]),
    [importBusy, setImportBusy] = useState(false),
    [feedback, setFeedback] = useState(0);
  const [editDoc, setEditDoc] = useState<Dict | null>(null);
  const [scenario, setScenario] = useState<Dict | null>(null),
    [principal, setPrincipal] = useState("100000000"),
    [delta, setDelta] = useState("1"),
    [months, setMonths] = useState("12");
  const requestId = useRef(0),
    detailId = useRef(0);
  const active = companies.find((c) => c.id === company);
  const notify = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(""), 5000);
  };
  async function reloadStatus() {
    const s = await api("/status");
    setStatus(s);
    return s;
  }
  async function init() {
    try {
      await reloadStatus();
      const cs = await api("/companies");
      setCompanies(cs);
      setCompany((x) =>
        cs.some((c: Dict) => c.id === x) ? x : cs[0]?.id || "",
      );
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    const fn = () => setAuth(true);
    window.addEventListener("auth-required", fn);
    init();
    return () => window.removeEventListener("auth-required", fn);
  }, []);
  useEffect(() => {
    if (!company) return;
    const id = ++requestId.current;
    setLoading(true);
    setError("");
    api(
      `/feed?company_id=${encodeURIComponent(company)}&role=${role}&topic=${topic}&bookmarked=${page === "saved"}`,
    )
      .then((r) => {
        if (id === requestId.current) setEvents(r);
      })
      .catch((e) => {
        if (id === requestId.current) setError(e.message);
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
    setSelected(null);
    setResult(null);
    detailId.current++;
  }, [company, role, topic, page]);
  useEffect(() => {
    if (page === "sources")
      api("/documents")
        .then(setDocs)
        .catch((e) => setError(e.message));
    if (page === "activity")
      api("/metrics")
        .then(setMetrics)
        .catch((e) => setError(e.message));
  }, [page, status]);
  useEffect(() => {
    if (!search.trim()) return;
    const t = setTimeout(
      () =>
        api("/companies?q=" + encodeURIComponent(search))
          .then((r) =>
            setCompanies((old) => [
              ...r,
              ...old.filter((x) => !r.some((y: Dict) => y.id === x.id)),
            ]),
          )
          .catch((e) => notify(e.message)),
      300,
    );
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => {
    if (!selected && !modal) return;
    const fn = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelected(null);
        setModal("");
        detailId.current++;
      }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [selected, modal]);
  async function openEvent(event: Dict) {
    const id = ++detailId.current;
    setSelected(event);
    setResult(null);
    setBusy(true);
    setChat([]);
    setQuestion("");
    setDetailTab("analysis");
    setFeedback(0);
    try {
      const r = await post("/analyze", {
        company_id: company,
        event_id: event.id,
        role,
      });
      if (id === detailId.current) setResult(r);
    } catch (e) {
      if (id === detailId.current) notify((e as Error).message);
    } finally {
      if (id === detailId.current) setBusy(false);
    }
  }
  async function bookmark(event: Dict) {
    try {
      await post("/bookmarks", {
        company_id: company,
        event_id: event.id,
        enabled: !event.bookmarked,
      });
      setEvents((xs) =>
        xs.map((x) =>
          x.id === event.id ? { ...x, bookmarked: !x.bookmarked } : x,
        ),
      );
      notify(
        event.bookmarked
          ? "Событие удалено из сохранённых"
          : "Событие сохранено",
      );
    } catch (e) {
      notify((e as Error).message);
    }
  }
  async function refresh() {
    setRefreshing(true);
    try {
      const r = await post("/sources/refresh", {});
      await reloadStatus();
      const list = await api(
        `/feed?company_id=${encodeURIComponent(company)}&role=${role}&topic=${topic}&bookmarked=${page === "saved"}`,
      );
      setEvents(list);
      notify(
        r.every((s: Dict) => s.status === "error")
          ? "Источники пока недоступны. Подробности в разделе «Источники»."
          : "Обновление завершено",
      );
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  }
  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || busy || !result) return;
    const q = question,
      id = detailId.current;
    setQuestion("");
    setBusy(true);
    setChat((xs) => [...xs, { question: q, pending: true }]);
    try {
      const r = await post("/analyze", {
        company_id: company,
        event_id: selected?.id,
        role,
        question: q,
        parent_id: result.id,
      });
      if (id === detailId.current) {
        setChat((xs) => [...xs.slice(0, -1), { question: q, result: r }]);
        setResult(r);
      }
    } catch (e) {
      if (id === detailId.current)
        setChat((xs) => [
          ...xs.slice(0, -1),
          { question: q, error: (e as Error).message },
        ]);
    } finally {
      if (id === detailId.current) setBusy(false);
    }
  }
  async function importFile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setImportBusy(true);
    try {
      const data = new FormData(e.currentTarget);
      const r = await api("/import", { method: "POST", body: data });
      notify(
        `Импорт завершён: ${r.imported ?? r.chunks ?? 0} записей / фрагментов`,
      );
      setModal("");
      await init();
      setDocs(await api("/documents"));
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setImportBusy(false);
    }
  }
  async function importEvent(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setImportBusy(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await post(data.url ? "/events/url" : "/events/test", data);
      notify("Материал добавлен и обработан");
      setModal("");
      await reloadStatus();
      setEvents(
        await api(
          `/feed?company_id=${encodeURIComponent(company)}&role=${role}`,
        ),
      );
      setTopic("");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setImportBusy(false);
    }
  }
  const closeDetail = () => {
    setSelected(null);
    detailId.current++;
    setBusy(false);
  };
  const visibleEvents = events.filter(
    (e) =>
      !search ||
      `${e.title} ${e.body}`.toLowerCase().includes(search.toLowerCase()),
  );
  const pageNames: Dict = {
    feed: "Обзор событий",
    saved: "Сохранённое",
    sources: "Источники и данные",
    activity: "Работа аналитика",
    settings: "Настройки",
  };
  return (
    <div className="shell">
      <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("feed");
          }}
        >
          <span className="alfa-mark">
            А<span />
          </span>
          <span>
            Альфа-Бизнес<small>КОНКУРСНЫЙ ПРОТОТИП</small>
          </span>
        </a>
        <div className="sidebar-section">ВАШ БИЗНЕС</div>
        <button
          className={"nav " + (page === "home" ? "active" : "")}
          onClick={() => {
            setPage("home");
            setMobile(false);
          }}
        >
          <LayoutDashboard size={19} />
          Главная
        </button>
        <div className="sidebar-section">АНАЛИТИКА</div>
        {[
          ["feed", "Бизнес Пульс", Activity],
          ["saved", "Сохранённое", Bookmark],
          ["sources", "Источники и данные", Database],
          ["activity", "Работа аналитика", BarChart3],
        ].map(([key, label, Icon]: any) => (
          <button
            key={key}
            className={"nav " + (page === key ? "active" : "")}
            onClick={() => {
              setPage(key);
              setSearch("");
              setMobile(false);
            }}
          >
            <Icon size={19} />
            {label}
            {key === "feed" && <span className="new-dot" />}
          </button>
        ))}
        <div className="sidebar-bottom">
          <div className="assistant-note">
            <div className="small-icon">
              <Sparkles size={18} />
            </div>
            <strong>От события — к решению</strong>
            <p>Аналитика с учётом вашей компании и роли</p>
            <button onClick={() => setModal("about")}>
              Как это работает <ArrowUpRight size={14} />
            </button>
          </div>
          <button
            className={"nav " + (page === "settings" ? "active" : "")}
            onClick={() => setPage("settings")}
          >
            <Settings2 size={19} />
            Настройки
          </button>
          <div className="sidebar-footer">Альфа Хак · 2026</div>
        </div>
      </aside>
      {mobile && (
        <div className="mobile-backdrop" onClick={() => setMobile(false)} />
      )}
      <main className="main">
        <header className="topbar">
          <button
            className="icon-button mobile-toggle"
            aria-label="Открыть меню"
            onClick={() => setMobile(!mobile)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            Альфа-Бизнес <ChevronRight size={14} />{" "}
            <b>{page === "home" ? "Главная" : pageNames[page]}</b>
          </div>
          <div className="topbar-right">
            <span className="secure-label">
              <ShieldCheck size={15} /> Контекст компании
            </span>
            <button
              className="icon-button"
              aria-label="О продукте"
              onClick={() => setModal("about")}
            >
              <HelpCircle size={20} />
            </button>
            <div className="avatar">
              {role === "ceo" ? "ГД" : role === "cfo" ? "ФД" : "КЗ"}
            </div>
          </div>
        </header>
        <div className="workspace">
          <div className="context-row">
            <div className="context-select">
              <Building2 size={18} />
              <select
                aria-label="Компания"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.synthetic ? " · демо" : ""}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} />
            </div>
            <div className="role-select">
              <BriefcaseBusiness size={16} />
              <select
                aria-label="Роль"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {Object.entries(roles).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} />
            </div>
            <button
              className="text-button profile-link"
              onClick={async () => {
                try {
                  setProfile(
                    await api("/companies/" + encodeURIComponent(company)),
                  );
                  setModal("profile");
                } catch (e) {
                  notify((e as Error).message);
                }
              }}
            >
              Профиль компании <ArrowUpRight size={14} />
            </button>
          </div>
          {error && (
            <div className="notice danger">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button onClick={init}>Повторить</button>
            </div>
          )}
          {status && !status.model_ready && (
            <div className="notice">
              <ShieldCheck size={17} />
              <span>
                {status.visual_demo ? <><b>Визуальная демонстрация.</b> Работает без установки. Все данные учебные; ответы подготовлены заранее. Живая AI-аналитика и загрузка данных доступны в серверной версии.</> : <><b>Демонстрационный режим.</b> Модель не подключена — доступен разбор по правилам. Учебные данные отмечены в карточках.</>}
              </span>
              <button onClick={() => setPage("settings")}>
                Подключение <ArrowRight size={14} />
              </button>
            </div>
          )}
          {page === "home" ? (
            <>
              <div className="page-title">
                <div className="eyebrow">ГЛАВНАЯ</div>
                <h1>Ваш бизнес — в фокусе</h1>
                <p>Конкурсный макет входа в интернет-банк</p>
              </div>
              <section className="bank-entry">
                <div>
                  <Tag tone="red">
                    <Activity size={13} /> БИЗНЕС ПУЛЬС
                  </Tag>
                  <h2>
                    Что меняется вокруг.
                    <br />
                    Что это значит для вас.
                  </h2>
                  <p>
                    Новости и аналитика в контексте вашей компании.
                    <br />
                    Риски, возможности и основания каждого вывода.
                  </p>
                  <button className="primary" onClick={() => setPage("feed")}>
                    Перейти к аналитике <ArrowRight size={18} />
                  </button>
                </div>
                <div className="entry-art">
                  <Activity size={120} strokeWidth={1} />
                  <span>
                    Персональный взгляд
                    <br />
                    на деловые события
                  </span>
                </div>
              </section>
              <div className="notice">
                <Building2 size={18} />
                Баланс, платежи и реальные банковские интеграции в конкурсном
                макете не моделируются.
              </div>
            </>
          ) : page === "feed" || page === "saved" ? (
            <>
              <div className="page-title title-actions">
                <div>
                  <div className="eyebrow">
                    <span className="pulse-dot" /> ПЕРСОНАЛЬНАЯ АНАЛИТИКА
                  </div>
                  <h1>
                    {page === "saved"
                      ? "Ваши сохранённые события"
                      : "Бизнес Пульс"}
                  </h1>
                  <p>
                    {page === "saved"
                      ? "Вернитесь к важному, когда будете готовы принять решение."
                      : "Не просто новости. Понимание того, как они влияют на ваш бизнес."}
                  </p>
                </div>
                <button
                  className="secondary"
                  onClick={refresh}
                  disabled={refreshing}
                >
                  {refreshing ? <Spinner /> : <RefreshCw size={16} />}Обновить
                </button>
              </div>
              {page === "feed" && (
                <>
                  <section className="hero">
                    <div className="hero-copy">
                      <span className="hero-label">
                        <Sparkles size={14} /> ВАШ КОНТЕКСТ. ВАШИ РЕШЕНИЯ.
                      </span>
                      <h2>
                        Главное для вашего бизнеса.
                        <br />С объяснением «почему».
                      </h2>
                      <p>
                        Внешние события, экспертиза банка и особенности
                        <br className="desktop" /> компании — в одной понятной
                        картине.
                      </p>
                      <button onClick={() => setModal("about")}>
                        Как формируется аналитика <ArrowUpRight size={16} />
                      </button>
                    </div>
                    <div className="hero-art">
                      <div className="orbit orbit-one" />
                      <div className="orbit orbit-two" />
                      <div className="art-note">
                        <span className="art-icon">
                          <Activity size={25} />
                        </span>
                        <div>
                          <small>ПЕРСОНАЛЬНЫЙ ФОКУС</small>
                          <b>
                            {active?.sector?.split(" ").slice(0, 3).join(" ") ||
                              "Ваша компания"}
                          </b>
                          <span>
                            <span className="green-dot" /> Контекст учтён
                          </span>
                        </div>
                        <Sparkles size={18} />
                      </div>
                      <div className="art-line">
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                      </div>
                    </div>
                  </section>
                  <div className="stats-grid">
                    <Stat
                      label="В вашей ленте"
                      value={events.length}
                      icon={<FileText size={18} />}
                      sub="С учётом компании и роли"
                    />
                    <Stat
                      label="Высокая релевантность"
                      value={events.filter((e) => e.score >= 60).length}
                      icon={<Zap size={18} />}
                      sub="По правилам ранжирования"
                    />
                    <Stat
                      label="Материалы банка"
                      value={status?.real_counts.documents ?? 0}
                      icon={<Building2 size={18} />}
                      sub="Реальные загруженные обзоры"
                    />
                    <Stat
                      label="Основания выводов"
                      value="Прозрачно"
                      icon={<ShieldCheck size={18} />}
                      sub="Источники и журнал действий"
                    />
                  </div>
                </>
              )}
              <section className="feed-section">
                <div className="section-heading">
                  <div>
                    <h2>
                      {page === "saved" ? "Сохранённое" : "Важное для вас"}{" "}
                      <span className="count">{visibleEvents.length}</span>
                    </h2>
                    <span>Приоритет учитывает профиль и роль пользователя</span>
                  </div>
                  <button
                    className="secondary compact"
                    onClick={() => setModal("news")}
                  >
                    <Plus size={16} />
                    Добавить новость
                  </button>
                </div>
                <div className="filter-row">
                  <div className="tabs">
                    <button
                      className={!topic ? "selected" : ""}
                      onClick={() => setTopic("")}
                    >
                      Все события
                    </button>
                    {["rates", "demand", "trade", "industry", "regulation"].map(
                      (t) => (
                        <button
                          className={topic === t ? "selected" : ""}
                          key={t}
                          onClick={() => setTopic(t)}
                        >
                          {topicNames[t]}
                        </button>
                      ),
                    )}
                  </div>
                  <label className="search-box">
                    <Search size={16} />
                    <input
                      placeholder="Найти событие"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      aria-label="Поиск событий"
                    />
                  </label>
                </div>
                {loading ? (
                  <div className="loading-state">
                    <Spinner />
                    Собираем контекст компании…
                  </div>
                ) : visibleEvents.length ? (
                  <div className="event-grid">
                    {visibleEvents.map((event) => {
                      const Icon = topicIcons[event.topics[0]] || Activity;
                      return (
                        <article className="event-card" key={event.id}>
                          <div className="card-top">
                            <div className={"topic-icon " + event.topics[0]}>
                              <Icon size={20} />
                            </div>
                            <div className="event-tags">
                              <Tag tone={event.score >= 60 ? "green" : "grey"}>
                                {event.score >= 60
                                  ? "Высокая значимость"
                                  : "Контекст"}{" "}
                                · {event.score}
                              </Tag>
                              {event.synthetic === 1 && (
                                <Tag tone="amber">Учебный</Tag>
                              )}
                            </div>
                            <button
                              className={
                                "icon-button bookmark " +
                                (event.bookmarked ? "marked" : "")
                              }
                              aria-label={
                                event.bookmarked
                                  ? "Убрать из сохранённых"
                                  : "Сохранить событие"
                              }
                              onClick={() => bookmark(event)}
                            >
                              <Bookmark
                                size={19}
                                fill={
                                  event.bookmarked ? "currentColor" : "none"
                                }
                              />
                            </button>
                          </div>
                          <div className="event-meta">
                            {event.source}
                            <span>·</span>
                            {date(event.published)}
                          </div>
                          <button
                            className="event-title"
                            onClick={() => openEvent(event)}
                          >
                            <h3>{event.title}</h3>
                          </button>
                          <p className="event-summary">{event.summary}</p>
                          <div className="why">
                            <Sparkles size={15} />
                            <div>
                              <b>Почему это важно для вас</b>
                              <p>{event.reasons[0]}</p>
                            </div>
                          </div>
                          <div className="card-bottom">
                            <span>{topicNames[event.topics[0]]}</span>
                            <button onClick={() => openEvent(event)}>
                              Разобрать влияние <ArrowRight size={16} />
                            </button>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <Empty
                    title={
                      page === "saved"
                        ? "Пока ничего не сохранено"
                        : "Событий пока нет"
                    }
                    text={
                      page === "saved"
                        ? "Нажмите на закладку в карточке интересующего события."
                        : "Обновите официальные источники, добавьте материал или измените фильтр."
                    }
                  />
                )}
              </section>
            </>
          ) : page === "sources" ? (
            <>
              <div className="page-title title-actions">
                <div>
                  <div className="eyebrow">ПРОВЕРЯЕМЫЕ ОСНОВАНИЯ</div>
                  <h1>Источники и данные</h1>
                  <p>
                    Официальные новости, аналитика банка и контекст клиента.
                  </p>
                </div>
                <button className="primary" onClick={() => setModal("import")}>
                  <Upload size={16} />
                  Импорт данных
                </button>
              </div>
              <div className="two-columns">
                <section className="panel">
                  <div className="panel-head">
                    <h2>Официальные источники</h2>
                    <button
                      className="icon-button"
                      aria-label="Обновить источники"
                      onClick={refresh}
                      disabled={refreshing}
                    >
                      {refreshing ? <Spinner /> : <RefreshCw size={17} />}
                    </button>
                  </div>
                  {[
                    {
                      id: "cbr",
                      name: "Банк России",
                      url: "https://www.cbr.ru/rss/RssNews",
                    },
                    {
                      id: "cbr-press",
                      name: "Банк России · пресс-релизы",
                      url: "https://www.cbr.ru/rss/RssPress",
                    },
                  ].map((f) => {
                    const s = status?.sources.find((x: Dict) => x.id === f.id);
                    return (
                      <div className="source-item" key={f.id}>
                        <div className="source-logo">
                          <Globe size={20} />
                        </div>
                        <div>
                          <strong>{f.name}</strong>
                          <p>{s?.detail || "Обновление ещё не выполнялось"}</p>
                          <small>
                            {s?.checked
                              ? "Проверено: " + date(s.checked)
                              : "RSS · официальный сайт"}
                          </small>
                        </div>
                        <Tag
                          tone={
                            s?.status === "ok"
                              ? "green"
                              : s?.status === "error"
                                ? "amber"
                                : "grey"
                          }
                        >
                          {s?.status === "ok"
                            ? "Доступен"
                            : s?.status === "error"
                              ? "Нет доступа"
                              : "Не проверен"}
                        </Tag>
                      </div>
                    );
                  })}
                  <div className="panel-note">
                    Дополнительно можно импортировать публикации с сайтов
                    Росстата, Минфина, Минэкономразвития и Альфа-Банка по
                    официальной HTTPS-ссылке.
                  </div>
                  <button
                    className="secondary"
                    onClick={() => setModal("news")}
                  >
                    <Plus size={15} />
                    Добавить материал
                  </button>
                </section>
                <section className="panel">
                  <h2>Данные компаний</h2>
                  <div className="big-number">
                    {money(status?.counts.companies ?? 0)} <span>профилей</span>
                  </div>
                  <div className="data-row">
                    <span>Реальные профили из кейса</span>
                    <b>{status?.real_counts.companies ?? 0}</b>
                  </div>
                  <div className="data-row">
                    <span>Строки платёжных связей</span>
                    <b>{money(status?.counts.payments ?? 0)}</b>
                  </div>
                  <div className="data-row">
                    <span>Единицы выручки</span>
                    <Tag
                      tone={status?.revenue_unit_confirmed ? "green" : "amber"}
                    >
                      {status?.revenue_unit_confirmed
                        ? "Подтверждены"
                        : "Нужно уточнение"}
                    </Tag>
                  </div>
                  <label className="search-box wide">
                    <Search size={16} />
                    <input
                      aria-label="Найти компанию"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Поиск компании по ID или отрасли"
                    />
                  </label>
                  <p className="muted">
                    Поиск обновляет список компаний в верхнем переключателе.
                    Неизвестные и конфликтующие поля сохраняются явно.
                  </p>
                </section>
              </div>
              <section className="panel documents">
                <div className="panel-head">
                  <h2>Библиотека аналитики</h2>
                  <Tag>{docs.length} материалов</Tag>
                </div>
                {docs.length ? (
                  docs.map((d) => (
                    <div className="document-row" key={d.id}>
                      <div className="doc-icon">
                        <FileText size={22} />
                      </div>
                      <div>
                        <strong>{d.title}</strong>
                        <p>
                          {date(d.published)} · {d.pages || 0} стр. · {d.chunks}{" "}
                          фрагментов {d.ocr_chunks > 0 ? "· OCR" : ""}
                        </p>
                      </div>
                      <Tag tone={d.synthetic ? "amber" : "green"}>
                        {d.synthetic ? "Учебный материал" : "Материал банка"}
                      </Tag>
                      {!d.synthetic && (
                        <button
                          className="icon-button"
                          aria-label="Уточнить дату документа"
                          onClick={() => {
                            setEditDoc(d);
                            setModal("docmeta");
                          }}
                        >
                          <Settings2 size={16} />
                        </button>
                      )}
                      {d.filename && (
                        <button
                          className="icon-button"
                          aria-label="Открыть PDF"
                          onClick={() =>
                            openPdf("/api/documents/" + d.id + "/file").catch(
                              (e) => notify(e.message),
                            )
                          }
                        >
                          <ExternalLink size={18} />
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  <Empty
                    title="Добавьте банковские обзоры"
                    text="Загрузите PDF из материалов кейса и укажите дату публикации. Дата необходима для использования в актуальном анализе."
                  />
                )}
              </section>
            </>
          ) : page === "activity" ? (
            <>
              <div className="page-title">
                <div className="eyebrow">НАБЛЮДАЕМОСТЬ</div>
                <h1>Работа аналитика</h1>
                <p>Измеримые результаты, обратная связь и действия системы.</p>
              </div>
              <div className="stats-grid">
                <Stat
                  label="AI-анализов"
                  value={metrics?.modes.llm ?? 0}
                  icon={<Sparkles size={18} />}
                  sub="Только вызовы подключённой LLM"
                />
                <Stat
                  label="Разборов по правилам"
                  value={metrics?.modes.rules ?? 0}
                  icon={<SlidersHorizontal size={18} />}
                  sub="Отдельно от результатов модели"
                />
                <Stat
                  label="Медиана обработки"
                  value={
                    metrics?.latency.median_ms == null
                      ? "—"
                      : metrics.latency.median_ms + " мс"
                  }
                  icon={<Clock3 size={18} />}
                  sub="По последним 200 анализам"
                />
                <Stat
                  label="Бюджет за сегодня"
                  value={
                    (status?.usage.charged_or_reserved_rub ?? 0).toFixed(2) +
                    " ₽"
                  }
                  icon={<BarChart3 size={18} />}
                  sub={`Лимит ${status?.daily_budget_rub ?? 500} ₽ · Москва`}
                />
              </div>
              <div className="notice">
                <ShieldCheck size={18} />
                {metrics?.quality_note}
              </div>
              <section className="panel">
                <h2>Последние анализы</h2>
                {metrics?.failures?.length > 0 && (
                  <details className="limitations">
                    <summary>
                      <AlertCircle size={16} />
                      Ошибки анализа: {metrics?.failures?.length}
                      <ChevronDown size={16} />
                    </summary>
                    {metrics?.failures?.map((f: Dict) => (
                      <p key={f.id}>
                        {date(f.created)} · {f.company_id} · {f.message}
                      </p>
                    ))}
                  </details>
                )}
                {metrics?.runs.length ? (
                  metrics.runs.map((r: Dict) => (
                    <details className="run-row" key={r.id}>
                      <summary>
                        <div>
                          <strong>
                            {companies.find((c) => c.id === r.company_id)
                              ?.name || r.company_id}
                          </strong>
                          <p>
                            {roles[r.role]} · {date(r.created)} · {r.elapsed_ms}{" "}
                            мс
                          </p>
                        </div>
                        <Tag tone={r.mode === "llm" ? "green" : "amber"}>
                          {r.mode === "llm" ? "Модель" : "Правила"}
                        </Tag>
                        <ChevronDown size={16} />
                      </summary>
                      <Trace trace={r.trace} />
                    </details>
                  ))
                ) : (
                  <Empty
                    title="Журнал пока пуст"
                    text="Откройте событие и запустите разбор влияния на компанию."
                  />
                )}
              </section>
            </>
          ) : (
            <>
              <div className="page-title">
                <div className="eyebrow">КОНФИГУРАЦИЯ</div>
                <h1>Настройки продукта</h1>
                <p>Текущее состояние подключения и возможности системы.</p>
              </div>
              <div className="two-columns">
                <section className="panel">
                  <Sparkles className="red-text" size={28} />
                  <h2>Разрешённая модель</h2>
                  <Tag tone={status?.model_ready ? "green" : "amber"}>
                    {status?.model_ready
                      ? status.model_family
                      : "Не подключена"}
                  </Tag>
                  <p>
                    В продукте используются только модели из приложения 3 кейса.
                    Доступ к шлюзу предоставляют организаторы.
                  </p>
                  <p className="muted">
                    Адрес API, ключ, точный ID модели и тарифы задаются на
                    сервере через <code>.env</code>. Ключ не сохраняется в
                    браузере и не попадает в журнал.
                  </p>
                  <div className="code-block">
                    LLM_BASE_URL
                    <br />
                    LLM_API_KEY
                    <br />
                    LLM_MODEL_ID
                    <br />
                    LLM_MODEL_FAMILY
                    <br />
                    LLM_INPUT_RUB_PER_MILLION
                    <br />
                    LLM_OUTPUT_RUB_PER_MILLION
                  </div>
                  <p className="muted">
                    Лимит — не более 500 ₽ в сутки. До настройки доступны только
                    явно обозначенные разборы по правилам.
                  </p>
                </section>
                <section className="panel">
                  <ShieldCheck size={28} className="green-text" />
                  <h2>Контроль и ограничения</h2>
                  {[
                    "Только официальные HTTPS-источники",
                    "Никаких реальных банковских операций",
                    "Изоляция ответов по компании и роли",
                    "Проверка дат, цитат и числовых утверждений",
                    "Учебные материалы всегда обозначены",
                    "Ключи хранятся только на сервере",
                  ].map((x) => (
                    <div className="check-line" key={x}>
                      <Check size={16} />
                      {x}
                    </div>
                  ))}
                  <div className="notice">
                    {status?.access_protected
                      ? "Включён общий код доступа к конкурсному стенду."
                      : "Стенд открыт. Перед размещением в интернете настройте APP_ACCESS_TOKEN и HTTPS."}
                  </div>
                </section>
              </div>
            </>
          )}
          <footer className="page-footer">
            <span>
              <Activity size={14} /> Бизнес Пульс
            </span>
            <span>
              Конкурсный прототип · Выводы требуют оценки пользователя
            </span>
          </footer>
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <AlertCircle size={18} />
          {toast}
          <button aria-label="Закрыть уведомление" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {selected && (
        <div className="overlay" onClick={closeDetail}>
          <section
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Анализ события"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <button className="text-button" onClick={closeDetail}>
                <ArrowLeft size={16} />
                Назад к событиям
              </button>
              <button
                className="icon-button"
                aria-label="Закрыть анализ"
                onClick={closeDetail}
              >
                <X size={21} />
              </button>
            </div>
            <div className="drawer-content">
              <div className="eyebrow">
                {topicNames[selected.topics[0]]} · {date(selected.published)}
              </div>
              <h1>{selected.title}</h1>
              <div className="detail-meta">
                <Tag tone="red">{active?.name}</Tag>
                <Tag>{roles[role]}</Tag>
                {selected.synthetic === 1 && (
                  <Tag tone="amber">Синтетическое событие</Tag>
                )}
              </div>
              <div className="tabs detail-tabs">
                {[
                  ["analysis", "Влияние на бизнес"],
                  ["evidence", "Источники"],
                  ["trace", "Действия агента"],
                ].map(([k, v]) => (
                  <button
                    key={k}
                    className={detailTab === k ? "selected" : ""}
                    onClick={() => setDetailTab(k)}
                  >
                    {v}
                  </button>
                ))}
              </div>
              {busy && !result ? (
                <div className="analysis-loading">
                  <div className="loading-orb">
                    <Sparkles size={29} />
                  </div>
                  <h3>Соединяем событие с вашим бизнесом</h3>
                  <p>Профиль компании → поиск оснований → проверка выводов</p>
                  <Spinner />
                </div>
              ) : !result ? (
                <Empty
                  title="Анализ не получен"
                  text="Посмотрите уведомление об ошибке и повторите после устранения причины."
                />
              ) : detailTab === "trace" ? (
                <>
                  <div className="notice">
                    {result.mode === "llm"
                      ? "Собственная агентная логика с подключённой моделью"
                      : "Выполнен контроллер инструментов. LLM не подключена — результат сформирован правилами."}{" "}
                    · {result.elapsed_ms} мс {result.cached ? "· из кэша" : ""}
                  </div>
                  <Trace trace={result.trace} />
                </>
              ) : detailTab === "evidence" ? (
                <>
                  {result.evidence.map((e: Dict) => (
                    <div className="evidence-card" key={e.id}>
                      <div>
                        <Tag tone={e.synthetic ? "amber" : "grey"}>
                          {e.type === "bank"
                            ? "Материал банка"
                            : e.type === "news"
                              ? "Событие"
                              : e.type === "payments"
                                ? "Платёжные связи"
                                : "Профиль"}
                          {e.synthetic ? " · учебный" : ""}
                        </Tag>
                        <span className="muted">
                          {e.published ? date(e.published) : ""}
                          {e.page ? " · стр. " + e.page : ""}
                        </span>
                      </div>
                      <h3>{e.title}</h3>
                      <p>{e.text}</p>
                      <code>{e.id}</code>
                      {e.url && <SourceLink source={e} onError={notify} />}
                    </div>
                  ))}
                </>
              ) : (
                <>
                  <div
                    className={
                      "notice " + (result.mode === "rules" ? "" : "success")
                    }
                  >
                    <Sparkles size={18} />
                    {result.mode === "rules"
                      ? "Разбор по правилам, без LLM. Это демонстрация сценария, а не результат AI-модели."
                      : `Вывод модели ${status?.model_family}. Отделён от фактов и позиции банка.`}
                  </div>
                  <section className="analysis-block">
                    <div className="block-title">
                      <FileText size={18} />
                      <h2>Что произошло</h2>
                    </div>
                    <p>{selected.body}</p>
                    {selected.url && (
                      <a
                        className="source-link"
                        href={selected.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {selected.source}
                        <ExternalLink size={13} />
                      </a>
                    )}
                  </section>
                  <ClaimSection
                    title="Почему это важно для вашей компании"
                    icon={<Sparkles size={19} />}
                    claims={result.answer.explanation}
                    onSource={() => setDetailTab("evidence")}
                  />
                  <section className="bank-position">
                    <div className="block-title">
                      <Building2 size={19} />
                      <h2>Как это оценивает банк</h2>
                    </div>
                    {result.bank_position.filter((b: Dict) => !b.synthetic)
                      .length ? (
                      result.bank_position
                        .filter((b: Dict) => !b.synthetic)
                        .slice(0, 2)
                        .map((b: Dict) => (
                          <div key={b.id}>
                            <blockquote>{b.text}</blockquote>
                            <SourceLink source={b} onError={notify} />
                            {b.stale && (
                              <Tag tone="amber">
                                Старше 120 дней · исторический контекст
                              </Tag>
                            )}
                          </div>
                        ))
                    ) : (
                      <p>
                        Подходящая позиция Альфа-Банка по загруженным
                        датированным материалам не найдена. Учебные тексты не
                        выдаются за мнение банка.
                      </p>
                    )}
                  </section>
                  <div className="risk-opportunity">
                    <ClaimSection
                      title="Возможные риски"
                      icon={<ArrowDown size={18} />}
                      claims={result.answer.risks}
                      onSource={() => setDetailTab("evidence")}
                      tone="risk"
                    />
                    <ClaimSection
                      title="Возможности"
                      icon={<TrendingUp size={18} />}
                      claims={result.answer.opportunities}
                      onSource={() => setDetailTab("evidence")}
                      tone="opportunity"
                    />
                  </div>
                  <ClaimSection
                    title="Что можно сделать"
                    icon={<CheckCircle2 size={18} />}
                    claims={result.answer.actions}
                    onSource={() => setDetailTab("evidence")}
                  />
                  <button
                    className="scenario-link"
                    onClick={() => {
                      setScenario(null);
                      setModal("scenario");
                    }}
                  >
                    <SlidersHorizontal size={17} />
                    <div>
                      <b>Проверить сценарий финансирования</b>
                      <span>
                        Рассчитать влияние изменения ставки на ваших параметрах
                      </span>
                    </div>
                    <ArrowUpRight size={18} />
                  </button>
                  <details className="limitations">
                    <summary>
                      <ShieldCheck size={16} />
                      Что известно не полностью
                      <ChevronDown size={16} />
                    </summary>
                    {result.answer.limitations.map((s: string, i: number) => (
                      <p key={i}>{s}</p>
                    ))}
                    {result.answer.questions.map((s: string, i: number) => (
                      <button
                        key={i}
                        onClick={() => {
                          setQuestion(s);
                          document.getElementById("question-input")?.focus();
                        }}
                      >
                        {s}
                        <MessageCircle size={14} />
                      </button>
                    ))}
                  </details>
                  <div className="feedback">
                    <span>Разбор был полезен?</span>
                    {[1, -1].map((v) => (
                      <button
                        key={v}
                        disabled={feedback !== 0}
                        className={feedback === v ? "rated" : ""}
                        aria-label={v === 1 ? "Полезно" : "Не полезно"}
                        onClick={async () => {
                          try {
                            await post("/feedback", {
                              run_id: result.id,
                              rating: v,
                              reason:
                                v === -1 ? "Неполезный или неполный вывод" : "",
                            });
                            setFeedback(v);
                            notify("Спасибо, оценка сохранена");
                          } catch (e) {
                            notify((e as Error).message);
                          }
                        }}
                      >
                        {v === 1 ? (
                          <ThumbsUp size={17} />
                        ) : (
                          <ThumbsDown size={17} />
                        )}
                      </button>
                    ))}
                  </div>
                  <section className="chat-section">
                    <h2>
                      <MessageCircle size={19} />
                      Уточнить по событию
                    </h2>
                    <p className="muted">
                      Ответ учитывает текущую компанию, роль и разобранное
                      событие.
                    </p>
                    {chat.map((m, i) => (
                      <div className="chat-pair" key={i}>
                        <div className="chat-question">{m.question}</div>
                        {m.pending ? (
                          <div className="chat-answer">
                            <Spinner /> Готовим ответ…
                          </div>
                        ) : m.error ? (
                          <div className="notice danger">{m.error}</div>
                        ) : (
                          <div className="chat-answer">
                            {m.result.mode === "rules" && (
                              <Tag tone="amber">Ответ по правилам</Tag>
                            )}
                            {m.result.answer.explanation.map(
                              (c: Dict, j: number) => (
                                <p key={j}>{c.text}</p>
                              ),
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                    <form className="question-form" onSubmit={ask}>
                      <input
                        id="question-input"
                        aria-label="Уточняющий вопрос"
                        value={question}
                        maxLength={1500}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder="Например: что проверить в кредитном договоре?"
                      />
                      <button
                        className="primary square"
                        disabled={busy || !question.trim()}
                        aria-label="Отправить вопрос"
                      >
                        {busy ? <Spinner /> : <Send size={18} />}
                      </button>
                    </form>
                  </section>
                </>
              )}
            </div>
          </section>
        </div>
      )}
      {modal && (
        <div
          className="overlay modal-overlay"
          onClick={() => {
            if (!importBusy) setModal("");
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Действие"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h2>
                {
                  {
                    about: "Как работает Бизнес Пульс",
                    profile: "Контекст компании",
                    import: "Импорт исходных данных",
                    news: "Новый материал",
                    scenario: "Сценарный расчёт",
                    docmeta: "Метаданные материала",
                  }[modal]
                }
              </h2>
              <button
                className="icon-button"
                disabled={importBusy}
                aria-label="Закрыть окно"
                onClick={() => setModal("")}
              >
                <X size={21} />
              </button>
            </div>
            {modal === "about" ? (
              <>
                <p>
                  Сервис превращает внешние события в персональную аналитику.
                  Основа — данные компании, выбранная роль и проверяемые
                  источники.
                </p>
                {[
                  [
                    "01",
                    "Контекст",
                    "Основная деятельность, регион, продукты банка, внешнеторговые и платёжные связи.",
                  ],
                  [
                    "02",
                    "Отбор",
                    "События ранжируются по признакам компании и приоритетам роли. Балл — оценка по правилам, не вероятность.",
                  ],
                  [
                    "03",
                    "Анализ",
                    "Собственный контроллер планирует действия, ищет материалы, проверяет даты и ссылки, повторяет поиск при нехватке оснований.",
                  ],
                  [
                    "04",
                    "Прозрачность",
                    "Факт, выдержка из аналитики банка и условная интерпретация показаны отдельно.",
                  ],
                ].map(([n, t, p]) => (
                  <div className="how-step" key={n}>
                    <span>{n}</span>
                    <div>
                      <h3>{t}</h3>
                      <p>{p}</p>
                    </div>
                  </div>
                ))}
                <div className="notice">
                  Это самостоятельный конкурсный прототип. Реальные банковские
                  операции и интеграция с Альфа-Бизнесом отсутствуют.
                </div>
              </>
            ) : modal === "profile" && profile ? (
              <>
                <div className="profile-heading">
                  <Building2 size={27} />
                  <div>
                    <h3>{profile.name}</h3>
                    <span>{profile.id}</span>
                  </div>
                  {profile.synthetic === 1 && (
                    <Tag tone="amber">Синтетический профиль</Tag>
                  )}
                </div>
                {[
                  ["Деятельность", profile.sector],
                  ["Регион регистрации", profile.region],
                  [
                    "Выручка",
                    money(profile.revenue) +
                      (profile.synthetic
                        ? " ₽ · учебная"
                        : status?.revenue_unit_confirmed
                          ? " ₽"
                          : " · единицы не подтверждены"),
                  ],
                  [
                    "Кредитный продукт",
                    profile.credit === 1
                      ? "Есть"
                      : profile.credit === 0
                        ? "Не отмечен"
                        : "Неизвестно",
                  ],
                  ["Страны ФТС", profile.fts || "Не указаны"],
                  ["Группа", profile.group_id || "Не указана"],
                  ["Наблюдаемые контрагенты", profile.payments.counterparties],
                  [
                    "Контрагенты без профиля",
                    profile.payments.missing_profiles ?? 0,
                  ],
                ].map(([k, v]) => (
                  <div className="data-row" key={k}>
                    <span>{k}</span>
                    <b>{v || "Не указано"}</b>
                  </div>
                ))}
                {profile.conflicts.length > 0 && (
                  <div className="notice danger">
                    Конфликтующие поля: {profile.conflicts.join(", ")}
                  </div>
                )}
                <div className="notice">
                  Доля рынка неизвестна. Связи не доказывают владение или
                  поставки. Выручка группы не суммируется.
                </div>
              </>
            ) : modal === "import" ? (
              <form onSubmit={importFile} className="form-stack">
                <p>
                  Загрузите исходные CSV или PDF банковской аналитики.
                  Существующие записи сохраняются; повторный импорт того же
                  файла не создаёт дубли.
                </p>
                <label>
                  Тип данных
                  <select name="kind">
                    <option value="companies">
                      Профили компаний · df_Uid_data_hack.csv
                    </option>
                    <option value="payments">
                      Платёжные связи · df_Uid_payment_hack.csv
                    </option>
                    <option value="links">
                      Связи физлиц · df_Fid_Uid_link_hack.csv
                    </option>
                    <option value="bank">Банковская аналитика · PDF</option>
                  </select>
                </label>
                <label>
                  Файл
                  <input name="file" type="file" accept=".csv,.pdf" required />
                </label>
                <label>
                  Название материала (для PDF)
                  <input name="title" placeholder="Название обзора банка" />
                </label>
                <label>
                  Дата публикации PDF
                  <input
                    name="published"
                    type="date"
                    max={new Date().toLocaleDateString("en-CA")}
                  />
                </label>
                <label>
                  Ссылка на оригинал (для PDF)
                  <input
                    name="url"
                    type="url"
                    placeholder="https://alfabank.ru/…"
                  />
                </label>
                <div className="notice">
                  Без даты документ сохраняется, но не используется в текущей
                  интерпретации. Для сканов нужен OCR.
                </div>
                <button className="primary" disabled={importBusy}>
                  {importBusy ? <Spinner /> : <Upload size={17} />}{" "}
                  {importBusy ? "Обработка файла…" : "Импортировать"}
                </button>
              </form>
            ) : modal === "news" ? (
              <>
                <form className="form-stack" onSubmit={importEvent}>
                  <p>
                    Загрузите ранее не использованную публикацию с официального
                    сайта.
                  </p>
                  <label>
                    HTTPS-ссылка на публикацию
                    <input
                      name="url"
                      type="url"
                      placeholder="https://www.cbr.ru/…"
                      required
                    />
                  </label>
                  <label>
                    Дата публикации, если не определится автоматически
                    <input name="published" type="date" />
                  </label>
                  <button className="primary" disabled={importBusy}>
                    {importBusy ? <Spinner /> : <Globe size={16} />}Получить из
                    источника
                  </button>
                </form>
                <details className="test-import">
                  <summary>Добавить тестовый текст для проверки</summary>
                  <form className="form-stack" onSubmit={importEvent}>
                    <div className="notice">
                      Вставленный текст всегда помечается как тестовый,
                      независимо от содержания.
                    </div>
                    <label>
                      Заголовок
                      <input
                        name="title"
                        minLength={10}
                        maxLength={300}
                        required
                      />
                    </label>
                    <label>
                      Дата
                      <input name="published" type="date" required />
                    </label>
                    <label>
                      Текст
                      <textarea
                        name="body"
                        rows={5}
                        minLength={80}
                        maxLength={30000}
                        required
                      />
                    </label>
                    <button className="secondary" disabled={importBusy}>
                      {importBusy ? <Spinner /> : <Plus size={16} />}Добавить
                      тестовый материал
                    </button>
                  </form>
                </details>
              </>
            ) : modal === "docmeta" && editDoc ? (
              <form
                className="form-stack"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const data = Object.fromEntries(
                    new FormData(e.currentTarget),
                  );
                  try {
                    await post("/documents/" + editDoc.id + "/metadata", data);
                    setDocs(await api("/documents"));
                    await reloadStatus();
                    setModal("");
                    notify("Метаданные сохранены");
                  } catch (e) {
                    notify((e as Error).message);
                  }
                }}
              >
                <div className="notice">
                  Указывайте дату из самого документа. Она определяет, может ли
                  материал участвовать в текущем анализе.
                </div>
                <label>
                  Название
                  <input
                    name="title"
                    defaultValue={editDoc.title}
                    required
                    minLength={3}
                    maxLength={300}
                  />
                </label>
                <label>
                  Дата публикации
                  <input
                    name="published"
                    type="date"
                    defaultValue={editDoc.published || ""}
                    required
                  />
                </label>
                <button className="primary">
                  Сохранить <Check size={16} />
                </button>
              </form>
            ) : modal === "scenario" ? (
              <form
                className="form-stack"
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    setScenario(
                      await post("/scenario", {
                        principal: Number(principal),
                        delta_pp: Number(delta),
                        months: Number(months),
                      }),
                    );
                  } catch (e) {
                    notify((e as Error).message);
                  }
                }}
              >
                <div className="notice">
                  Условный сценарий по введённым данным. Это не оценка
                  фактического долга компании.
                </div>
                <label>
                  Основной долг (в вашей валюте)
                  <input
                    type="number"
                    min="1"
                    max="1000000000000000"
                    required
                    value={principal}
                    onChange={(e) => setPrincipal(e.target.value)}
                  />
                </label>
                <label>
                  Изменение ставки, процентных пунктов
                  <input
                    type="number"
                    step="0.01"
                    min="-100"
                    max="100"
                    required
                    value={delta}
                    onChange={(e) => setDelta(e.target.value)}
                  />
                </label>
                <label>
                  Период, месяцев
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="120"
                    required
                    value={months}
                    onChange={(e) => setMonths(e.target.value)}
                  />
                </label>
                <button className="primary">
                  Рассчитать <ArrowRight size={16} />
                </button>
                {scenario && (
                  <div className="scenario-result">
                    <span>Изменение расходов за период</span>
                    <h2>
                      {new Intl.NumberFormat("ru-RU").format(
                        scenario.period_delta,
                      )}
                    </h2>
                    <p>
                      В валюте введённой суммы. Отрицательное значение —
                      снижение расходов.
                    </p>
                    {scenario.assumptions.map((s: string) => (
                      <small key={s}>{s}</small>
                    ))}
                  </div>
                )}
              </form>
            ) : null}
          </section>
        </div>
      )}
      {auth && (
        <div className="overlay modal-overlay">
          <section className="modal">
            <div className="eyebrow">БИЗНЕС ПУЛЬС</div>
            <h2>Вход в конкурсный стенд</h2>
            <p>Введите общий код доступа, настроенный владельцем сервера.</p>
            <form
              className="form-stack"
              onSubmit={async (e) => {
                e.preventDefault();
                sessionStorage.setItem("pulse_access", authCode);
                try {
                  await api("/status");
                  setAuth(false);
                  await init();
                } catch {
                  notify("Код доступа не подошёл");
                }
              }}
            >
              <input
                aria-label="Код доступа"
                type="password"
                autoFocus
                value={authCode}
                onChange={(e) => setAuthCode(e.target.value)}
                required
              />
              <button className="primary">
                Продолжить <ArrowRight size={16} />
              </button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
  sub,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  sub: string;
}) {
  return (
    <div className="stat">
      <div className="stat-label">
        {label}
        {icon}
      </div>
      <strong>{value}</strong>
      <p>{sub}</p>
    </div>
  );
}
function Trace({ trace }: { trace: Dict[] }) {
  return (
    <div className="trace">
      {trace.map((s: Dict) => (
        <div className="trace-step" key={s.step}>
          <div className={"trace-number " + s.status}>
            {s.status === "warning" ? <AlertCircle size={16} /> : s.step}
          </div>
          <div>
            <h3>{s.action}</h3>
            <p>{s.detail}</p>
            <small>{new Date(s.at).toLocaleTimeString("ru-RU")}</small>
          </div>
        </div>
      ))}
    </div>
  );
}
function ClaimSection({
  title,
  icon,
  claims,
  onSource,
  tone = "",
}: {
  title: string;
  icon: React.ReactNode;
  claims: Dict[];
  onSource: () => void;
  tone?: string;
}) {
  return (
    <section className={"analysis-block " + tone}>
      <div className="block-title">
        {icon}
        <h2>{title}</h2>
      </div>
      {claims.length ? (
        claims.map((c, i) => (
          <div className="claim" key={i}>
            <p>{c.text}</p>
            <button onClick={onSource}>
              <FileText size={12} />
              {c.evidence_ids.length} основания
            </button>
          </div>
        ))
      ) : (
        <p className="muted">По имеющимся данным не установлены.</p>
      )}
    </section>
  );
}
function SourceLink({
  source,
  onError,
}: {
  source: Dict;
  onError: (s: string) => void;
}) {
  return source.synthetic ? (
    <span className="muted">Учебный текст · не позиция банка</span>
  ) : source.url?.startsWith("/api/") ? (
    <button
      className="source-link"
      onClick={() => openPdf(source.url).catch((e) => onError(e.message))}
    >
      {source.title} · {date(source.published)} · стр. {source.page}
      <ExternalLink size={13} />
    </button>
  ) : source.url ? (
    <a
      className="source-link"
      href={source.url}
      target="_blank"
      rel="noreferrer"
    >
      Первоисточник <ExternalLink size={13} />
    </a>
  ) : null;
}

createRoot(document.getElementById("root")!).render(<App />);
