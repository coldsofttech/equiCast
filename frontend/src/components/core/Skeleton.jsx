import "./Skeleton.css";

/**
 * A shimmering placeholder block for content that hasn't loaded yet.
 * `width`/`height` are plain CSS values (e.g. "60%", "1.5rem"); `circle`
 * rounds it fully for avatar-style placeholders. Purely decorative —
 * `aria-hidden` so screen readers skip it rather than announcing an empty
 * block.
 */
function Skeleton({ width = "100%", height = "1em", circle = false, className }) {
  return (
    <span
      className={["ec-skeleton", circle ? "is-circle" : "", className].filter(Boolean).join(" ")}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export default Skeleton;
