import { Component } from "react";
import AppErrorPage from "../../pages/errors/AppErrorPage.jsx";

/**
 * Catches a render-time crash anywhere in the wrapped tree and shows
 * AppErrorPage instead of leaving the tab blank — React error boundaries
 * must be class components, there's no hook equivalent. Only catches
 * errors thrown while rendering/in lifecycle methods; React never routes
 * an event-handler or effect's own thrown error here (each of those
 * already has its own try/catch at the call site, e.g. every page's own
 * `loadError` state), nor an async rejection after the render that
 * triggered it has already committed.
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
      return <AppErrorPage />;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
