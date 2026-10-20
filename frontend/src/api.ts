export const access = () => sessionStorage.getItem("pulse_access") || "";
export async function api(path: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${access()}`,
  };
  if (init.body && !(init.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const r = await fetch("/api" + path, {
    ...init,
    headers: { ...headers, ...init.headers },
  });
  if (r.status === 401) {
    window.dispatchEvent(new Event("auth-required"));
    throw new Error("Введите код доступа");
  }
  if (!r.ok) {
    let message = "Не удалось выполнить запрос";
    try {
      const d = await r.json();
      message =
        typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {}
    throw new Error(message);
  }
  return r.json();
}
export const post = (path: string, body: unknown) =>
  api(path, { method: "POST", body: JSON.stringify(body) });
export async function openPdf(path: string) {
  const [base, fragment] = path.split("#");
  const r = await fetch(base, {
    headers: { Authorization: `Bearer ${access()}` },
  });
  if (!r.ok) throw new Error("Файл недоступен");
  const url = URL.createObjectURL(await r.blob());
  window.open(url + (fragment ? "#" + fragment : ""), "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
