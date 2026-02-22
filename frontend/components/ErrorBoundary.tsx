'use client';

import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  showDetails: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
          <AlertTriangle className="h-16 w-16 text-destructive mb-6" />
          <h2 className="text-2xl font-bold mb-2">Something went wrong</h2>
          <p className="text-muted-foreground max-w-md mb-6">
            An unexpected error occurred. Please try reloading the page.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => window.location.reload()}>Reload Page</Button>
            <Button
              variant="outline"
              onClick={() => this.setState((prev) => ({ showDetails: !prev.showDetails }))}
            >
              {this.state.showDetails ? 'Hide Details' : 'Show Details'}
            </Button>
          </div>
          {this.state.showDetails && this.state.error && (
            <pre className="mt-6 max-w-2xl w-full overflow-auto rounded-md bg-muted p-4 text-left text-sm text-muted-foreground">
              {this.state.error.message}
              {'\n\n'}
              {this.state.error.stack}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
