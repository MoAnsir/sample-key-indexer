import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="card border-warn/30 m-4">
            <p className="text-sm font-sans font-semibold text-warn">
              Something went wrong
            </p>
            <p className="text-xs text-muted mt-1 font-mono">
              {this.state.error.message}
            </p>
            <button
              onClick={() => this.setState({ error: null })}
              className="mt-2 text-xs text-accent underline font-sans"
            >
              Try again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
