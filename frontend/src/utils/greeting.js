/**
 * Time-of-day welcome message for /dashboard: a fixed classic title
 * ("Good morning/afternoon/evening/night, {name}") paired with a
 * randomly-picked friendly subtitle line for the same bucket, so the
 * subtitle varies without the title itself changing every visit.
 * buildGreeting picks the subtitle at random on every call;
 * getSessionGreeting (what DashboardPage actually uses) rolls it once and
 * pins it to sessionStorage so navigating away and back within the same
 * tab session keeps showing the same line instead of reshuffling.
 */
import { readCache, writeCache, clearCache } from "../api/sessionCache.js";

const CACHE_KEY = "ec_greeting";

// Spans midnight (21:00-04:59), so it's referenced by both the first and
// last bucket below rather than written out twice.
const NIGHT_SUBTITLES = [
  "Working late?",
  "Burning the midnight oil?",
  "Good to see you",
  "Hope you're having a good night",
  "Night owl mode?",
];

const BUCKETS = [
  {
    maxHour: 5,
    title: "Good night, {name}",
    subtitles: NIGHT_SUBTITLES,
  },
  {
    maxHour: 12,
    title: "Good morning, {name}",
    subtitles: [
      "Rise and shine",
      "Hope your morning's off to a good start",
      "Ready for the day?",
    ],
  },
  {
    maxHour: 17,
    title: "Good afternoon, {name}",
    subtitles: [
      "Hope you're having a good day",
      "Hope the afternoon's treating you well",
    ],
  },
  {
    maxHour: 21,
    title: "Good evening, {name}",
    subtitles: [
      "Hope you had a good day",
      "Winding down?",
      "Hope your evening's off to a nice start",
    ],
  },
  {
    maxHour: 24,
    title: "Good night, {name}",
    subtitles: NIGHT_SUBTITLES,
  },
];

function bucketForHour(hour) {
  return BUCKETS.find((bucket) => hour < bucket.maxHour);
}

/**
 * Builds the fixed title plus a random subtitle for the current hour, with
 * `firstName` filled into the title.
 * @param {string} firstName
 * @param {Date} [now]
 * @returns {{ title: string, subtitle: string }}
 */
export function buildGreeting(firstName, now = new Date()) {
  const bucket = bucketForHour(now.getHours());
  const subtitle = bucket.subtitles[Math.floor(Math.random() * bucket.subtitles.length)];
  return { title: bucket.title.replace("{name}", firstName), subtitle };
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
 * @returns {{ title: string, subtitle: string }}
 */
export function getSessionGreeting(user) {
  const cached = readCache(CACHE_KEY);
  if (cached?.title && cached?.subtitle) return cached;
  const next = buildGreeting(firstNameFrom(user));
  writeCache(CACHE_KEY, next);
  return next;
}

/** Clears the cached greeting — call on sign-out, see getSessionGreeting. */
export function clearCachedGreeting() {
  clearCache(CACHE_KEY);
}
