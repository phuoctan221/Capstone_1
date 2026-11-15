import { useEffect } from "react";

const ENABLED_KEY = "sv_daily_reminder_enabled";
const LAST_KEY = "sv_daily_reminder_last";

export function isReminderEnabled() {
  try {
    return localStorage.getItem(ENABLED_KEY) === "1";
  } catch {
    return false;
  }
}

export function canNotify() {
  return typeof window !== "undefined" && "Notification" in window;
}

export async function enableReminder() {
  if (!canNotify()) return false;
  let permission = Notification.permission;
  if (permission !== "granted") permission = await Notification.requestPermission();
  const granted = permission === "granted";
  try {
    localStorage.setItem(ENABLED_KEY, granted ? "1" : "0");
  } catch {
    return false;
  }
  return granted;
}

export function disableReminder() {
  try {
    localStorage.setItem(ENABLED_KEY, "0");
  } catch {
    // localStorage can be unavailable in private mode; ignore.
  }
}

export function useDailyReminder(plan) {
  useEffect(() => {
    if (!plan || !isReminderEnabled() || !canNotify()) return;
    if (Notification.permission !== "granted") return;
    if (plan.goal_met) return;

    const parts = [];
    if (plan.due_count > 0) parts.push(`${plan.due_count} từ cần ôn`);
    if (plan.remaining > 0) parts.push(`${plan.remaining} từ mới`);
    if (!parts.length) return;

    try {
      if (localStorage.getItem(LAST_KEY) === plan.date) return;
      new Notification("SmartVOCAB AI", {
        body: `Hôm nay: ${parts.join(" · ")}`,
        tag: "sv-daily-plan",
      });
      localStorage.setItem(LAST_KEY, plan.date);
    } catch {
      // Notifications are best-effort; the in-app plan still works.
    }
  }, [plan]);
}
