/**
 * Time-of-day welcome message for /dashboard. Each hour bucket mixes a few
 * different phrasings — classic ("Good afternoon"), a bare time-word
 * ("Noon"), and generic friendly lines ("Hope you're having a good day") —
 * so the greeting doesn't read as one template repeated with a different
 * name, plus a bootstrap-icons glyph + tone (warm for daylight buckets,
 * purple for night) DashboardPage renders before the text. buildGreeting
 * picks one at random on every call; getSessionGreeting (what DashboardPage
 * actually uses) rolls it once and pins it to sessionStorage so navigating
 * away and back within the same tab session keeps showing the same line
 * instead of reshuffling.
 */
import { readCache, writeCache, clearCache } from "../api/sessionCache.js";

const CACHE_KEY = "ec_greeting";

// Spans midnight (21:00-04:59), so it's referenced by both the first and
// last bucket below rather than written out twice.
const NIGHT_PHRASES = [
  "Working late, {name}?",
  "Burning the midnight oil, {name}?",
  "Good to see you, {name}",
  "Hope you're having a good night, {name}",
  "{name}, night owl mode?",
];

const BUCKETS = [
  {
    maxHour: 5,
    icon: "bi-moon-stars-fill",
    tone: "purple",
    phrases: NIGHT_PHRASES,
  },
  {
    maxHour: 12,
    icon: "bi-sunrise-fill",
    tone: "warning",
    phrases: [
      "Good morning, {name}",
      "Morning, {name}",
      "Rise and shine, {name}",
      "Hope your morning's off to a good start, {name}",
      "{name}, ready for the day?",
    ],
  },
  {
    maxHour: 17,
    icon: "bi-sun-fill",
    tone: "warning",
    phrases: [
      "Good afternoon, {name}",
      "Afternoon, {name}",
      "Noon, {name}",
      "Hope you're having a good day, {name}",
      "Hope the afternoon's treating you well, {name}",
    ],
  },
  {
    maxHour: 21,
    icon: "bi-sunset-fill",
    tone: "warning",
    phrases: [
      "Good evening, {name}",
      "Evening, {name}",
      "Hope you had a good day, {name}",
      "Winding down, {name}?",
      "{name}, hope your evening's off to a nice start",
    ],
  },
  {
    maxHour: 24,
    icon: "bi-moon-stars-fill",
    tone: "purple",
    phrases: NIGHT_PHRASES,
  },
];

function bucketForHour(hour) {
  return BUCKETS.find((bucket) => hour < bucket.maxHour);
}

/**
 * Picks a random phrase + icon/tone for the current hour and fills in
 * `firstName`.
 * @param {string} firstName
 * @param {Date} [now]
 * @returns {{ text: string, icon: string, tone: "warning" | "purple" }}
 */
export function buildGreeting(firstName, now = new Date()) {
  const bucket = bucketForHour(now.getHours());
  const template = bucket.phrases[Math.floor(Math.random() * bucket.phrases.length)];
  return { text: template.replace("{name}", firstName), icon: bucket.icon, tone: bucket.tone };
}

/**
 * First name for the greeting: Auth0's `given_name` claim when the
 * connection provides one, else the first word of the full `name` claim,
 * else a generic fallback for the rare case neither is set.
 * @param {{ given_name?: string, name?: string }} [user]
 * @returns {string}
 */
export function firstNameFrom(user) {
  if (user?.given_name) return user.given_name;
  const first = user?.name?.trim().split(/\s+/)[0];
  return first || "there";
}

/**
 * The greeting DashboardPage renders: built once per tab session and
 * cached in sessionStorage (same lifetime/tolerance-for-unavailable-storage
 * as useCurrentUser's profile cache), rather than rerolled on every mount —
 * so switching to another page and back doesn't change the message
 * mid-session. Call clearCachedGreeting() on sign-out (see UserMenu) so the
 * next sign-in on the same tab doesn't briefly show the previous user's
 * cached line before their own name loads.
 * @param {{ given_name?: string, name?: string }} [user]
 * @returns {{ text: string, icon: string, tone: "warning" | "purple" }}
 */
export function getSessionGreeting(user) {
  const cached = readCache(CACHE_KEY);
  if (cached?.text && cached?.icon) return cached;
  const next = buildGreeting(firstNameFrom(user));
  writeCache(CACHE_KEY, next);
  return next;
}

/** Clears the cached greeting — call on sign-out, see getSessionGreeting. */
export function clearCachedGreeting() {
  clearCache(CACHE_KEY);
}
