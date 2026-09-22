import { websiteIconUrl } from "../../utils/websiteIcon.js";
import "./AssetIcon.css";

/**
 * A market instrument's favicon, resolved from its `website` (see
 * websiteIconUrl) — shared by HoldingTickerPage's title icon (32px) and
 * TopbarSearch's result dropdown (16px) rather than each resolving/
 * rendering it separately. Renders a same-sized blank placeholder (rather
 * than nothing) when there's no website to derive an icon from (e.g. fx
 * pairs), so callers can render it unconditionally without the row's other
 * columns shifting to fill the gap in a flex/grid layout. `size` (px) sets
 * both the rendered dimensions and the resolution requested from the
 * favicon service (2x, for a crisp render on high-DPI screens) — many
 * sites only publish a favicon around 32-64px natively, so requesting well
 * past that (e.g. 2x a 40px display size) just has Google upscale a
 * low-res source, which looks blurrier than requesting a size closer to
 * what's actually likely available and letting the browser downscale it
 * instead.
 *
 * @param {{ website?: string|null, size?: number }} props
 */
function AssetIcon({ website, size = 24, className, ...rest }) {
  const iconUrl = websiteIconUrl(website, { size: size * 2 });
  const iconClassName = ["ec-asset-icon", className].filter(Boolean).join(" ");

  if (!iconUrl) {
    return (
      <span
        aria-hidden="true"
        className={iconClassName}
        style={{ width: size, height: size }}
        {...rest}
      />
    );
  }

  return (
    <img
      src={iconUrl}
      alt=""
      width={size}
      height={size}
      className={iconClassName}
      {...rest}
    />
  );
}

export default AssetIcon;
