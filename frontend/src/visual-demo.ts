import fixtures from "./visual-data.json";

// Deliberately separate from the server product: only synthetic fixtures,
// no network requests, no original case data, no model or credentials.
type Dict = Record<string, any>;
const data = fixtures as Dict;
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const bookmarks = new Set<string>();
const runs: Dict[] = [];
const ratings: number[] = [];
const unavailable = "Это визуальная демонстрация без сервера. Импорт файлов, получение новых публикаций и живая AI-аналитика доступны в серверной версии.";

export async function visualApi(path: string, init: RequestInit = {}) {
  const url = new URL(path, "https://visual-demo.invalid");
  const p = url.pathname;
  const query = url.searchParams;
  const body = typeof init.body === "string" ? JSON.parse(init.body) : {};
  if (p === "/status") {
    const state = clone(data.status);
    state.counts.runs = runs.length;
    return state;
  }
  if (p === "/health") return { status: "ok", mode: "visual" };
  if (p === "/companies") {
    const search = (query.get("q") || "").toLocaleLowerCase("ru");
    return clone(data.companies.filter((c: Dict) => `${c.name} ${c.id} ${c.sector}`.toLocaleLowerCase("ru").includes(search)));
  }
  if (p.startsWith("/companies/")) {
    const company = data.profiles[decodeURIComponent(p.slice(11))];
    if (!company) throw new Error("Компания не найдена");
    return clone(company);
  }
  if (p === "/feed") {
    const company = query.get("company_id");
    const events = clone<Dict[]>(data.feeds[company + ":" + (query.get("role") || "cfo")] || []);
    return events.map((event): Dict => ({ ...event, bookmarked: bookmarks.has(company + ":" + event.id) }))
      .filter((event) => !query.get("topic") || event.topics.includes(query.get("topic")))
      .filter((event) => query.get("bookmarked") !== "true" || event.bookmarked);
  }
  if (p === "/analyze") {
    const key = body.company_id + ":" + body.role + ":" + body.event_id;
    if (!data.analyses[key]) throw new Error("Учебный пример не найден");
    const result = clone(data.analyses[key]);
    result.id = "visual-" + (runs.length + 1);
    result.created = new Date().toISOString();
    result.cached = false;
    if (body.question) {
      result.question = body.question;
      result.answer.explanation = [{
        text: "Вопрос принят. В этой версии можно оценить внешний вид диалога. Свободный ответ AI появится в серверной версии после подключения разрешённой модели.",
        evidence_ids: ["company:" + body.company_id],
      }];
    }
    runs.unshift({ ...result, elapsed_ms: 0 });
    return result;
  }
  if (p === "/bookmarks") {
    const key = body.company_id + ":" + body.event_id;
    if (body.enabled) bookmarks.add(key); else bookmarks.delete(key);
    return { saved: true };
  }
  if (p === "/feedback") { ratings.push(body.rating); return { saved: true }; }
  if (p === "/documents") return clone(data.documents.map((d: Dict) => ({ ...d, pages: 1, chunks: 1 })));
  if (p === "/metrics") return {
    runs: clone(runs), latency: { median_ms: null, p95_ms: null },
    modes: { llm: 0, rules: runs.length }, failures: [],
    feedback: [-1, 1].map((rating) => ({ rating, count: ratings.filter((r) => r === rating).length })),
    quality_note: "Визуальная демонстрация на учебных данных. Это не измерения сервера или качества модели.",
  };
  if (p === "/scenario") {
    const amount = Number(body.principal), delta = Number(body.delta_pp), months = Number(body.months);
    if (!(amount > 0 && amount <= 1e15 && Math.abs(delta) <= 100 && months > 0 && months <= 120)) throw new Error("Проверьте параметры сценария");
    return {
      annual_delta: Math.round(amount * delta / 100 * 100) / 100,
      period_delta: Math.round(amount * delta / 100 * months / 12 * 100) / 100,
      assumptions: ["Параметры введены вами. Это не фактический долг компании.", "Неизменный основной долг и ставка на весь период; комиссии и погашение не учитываются."],
    };
  }
  throw new Error(unavailable);
}
