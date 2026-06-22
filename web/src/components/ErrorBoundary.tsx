import { Component, type ErrorInfo, type ReactNode } from "react";

// A view-level error boundary: if a view throws during render, show a recoverable fallback instead of
// unmounting the whole app (CodeRabbit #164). Resets when the `resetKey` (the active tab) changes.
interface Props { children: ReactNode; resetKey: string; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State { return { error }; }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("View render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <p className="center-msg" style={{ color: "var(--stale)" }}>
          Something went wrong rendering this view.<br />
          <span className="muted">{this.state.error.message}</span><br />
          <button className="filters" style={{ marginTop: 12 }} onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </p>
      );
    }
    return this.props.children;
  }
}
