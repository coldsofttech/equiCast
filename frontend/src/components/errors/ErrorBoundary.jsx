import { Component } from "react";

/**
 * Catches a render-time crash anywhere in the wrapped tree and shows
 * `fallback` instead of leaving the tab blank — React error boundaries
 * must be class components, there's no hook equivalent. Only catches
 * errors thrown while rendering/in lifecycle methods; React never routes
 * an event-handler or effect's own thrown error here (each of those
 * already has its own try/catch at the call site, e.g. every page's own
 * `loadError` state), nor an async rejection after the render that
 * triggered it has already committed.
 *
 * `fallback` is a prop rather than a hardcoded AppErrorPage import so
 * AppErrorPage itself can nest a second instance of this boundary around
 * its own AppShell/Topbar (see AppErrorPage.jsx) — that inner boundary's
 * fallback needs to be the plain standalone ErrorPage layout, not another
 * AppErrorPage, which would just re-render the same Topbar that may have
 * been what crashed in the first place.
 */
class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
