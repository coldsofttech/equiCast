import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import SettingsModal from "./SettingsModal.jsx";
import "./UserMenu.css";

function initialsFor(name, email) {
  const source = (name || email || "").trim();
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Topbar account menu: an avatar trigger that opens a dropdown with the
 * signed-in user's name/email (read straight off the Auth0 ID token via
 * `user` — no extra API round trip), "Accounts" (MenuBar has no direct
 * item for it — see menuItems.js), "Settings" (opens SettingsModal), and
 * the sign-out action. Only rendered inside AppShell, which only mounts
 * once RequireAuth has already confirmed `isAuthenticated`, so `user` is
 * always populated here.
 *
 * `profile`/`onProfileUpdate` are passed down from Topbar's own
 * useCurrentUser() call (rather than this component fetching its own copy)
 * so a currency change made here is reflected immediately in Topbar's
 * currency badge too.
 */
function UserMenu({ profile, onProfileUpdate }) {
  const { user, logout } = useAuth0();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    setImgFailed(false);
  }, [user?.picture]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handlePointerDown = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const name = user?.name;
  const email = user?.email;
  const initials = initialsFor(name, email);
  const showImage = Boolean(user?.picture) && !imgFailed;

  const handleSignOut = () => {
    logout({ logoutParams: { returnTo: window.location.origin } });
  };

  const renderAvatar = (size) => (
    <span className={`ec-avatar${size === "lg" ? " ec-avatar--lg" : ""}`} aria-hidden="true">
      {showImage ? (
        <img src={user.picture} alt="" onError={() => setImgFailed(true)} />
      ) : (
        initials
      )}
    </span>
  );

  return (
    <div className="ec-usermenu" ref={rootRef}>
      <button
        type="button"
        className="ec-usermenu-trigger"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label="Account"
      >
        {renderAvatar("sm")}
        <svg
          className="ec-usermenu-chevron"
          viewBox="0 0 24 24"
          width="12"
          height="12"
          fill="none"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {isOpen ? (
        <div className="ec-usermenu-panel" role="menu">
          <div className="ec-usermenu-head">
            {renderAvatar("lg")}
            <div className="ec-usermenu-who">
              <strong>{name || email || "Account"}</strong>
              {email && name ? <small>{email}</small> : null}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            className="ec-usermenu-item"
            onClick={() => {
              navigate("/accounts");
              setIsOpen(false);
            }}
          >
            <i className="bi bi-wallet2" aria-hidden="true" />
            Accounts
          </button>
          <button
            type="button"
            role="menuitem"
            className="ec-usermenu-item"
            onClick={() => {
              setIsSettingsOpen(true);
              setIsOpen(false);
            }}
          >
            <i className="bi bi-gear" aria-hidden="true" />
            Settings
          </button>
          <button
            type="button"
            role="menuitem"
            className="ec-usermenu-item ec-usermenu-item--danger"
            onClick={handleSignOut}
          >
            <i className="bi bi-box-arrow-right" aria-hidden="true" />
            Log out
          </button>
        </div>
      ) : null}

      <SettingsModal
        open={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        profile={profile}
        onSaved={onProfileUpdate}
      />
    </div>
  );
}

export default UserMenu;
