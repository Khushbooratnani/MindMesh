import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  AuthContextType,
  AuthState,
  SignInCredentials,
  SignUpCredentials,
} from './authTypes';
import { authService } from './authService';

const initialState: AuthState = {
  user: null,
  session: null,
  isLoading: true,
  isAuthenticated: false,
  error: null,
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>(initialState);

  // Restore active session on initial app mount
  useEffect(() => {
    let isMounted = true;
    const initAuth = async () => {
      try {
        const session = await authService.restoreSession();
        if (isMounted) {
          if (session) {
            setState({
              user: session.user,
              session,
              isLoading: false,
              isAuthenticated: true,
              error: null,
            });
          } else {
            setState({
              user: null,
              session: null,
              isLoading: false,
              isAuthenticated: false,
              error: null,
            });
          }
        }
      } catch {
        if (isMounted) {
          setState({
            user: null,
            session: null,
            isLoading: false,
            isAuthenticated: false,
            error: null,
          });
        }
      }
    };

    initAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const signIn = useCallback(async (credentials: SignInCredentials) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithEmail(credentials);
      setState({
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      });
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Authentication failed. Please check your credentials.',
      }));
      throw err;
    }
  }, []);

  const signUp = useCallback(async (credentials: SignUpCredentials) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signUpWithEmail(credentials);
      setState({
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      });
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Account creation failed. Please try again.',
      }));
      throw err;
    }
  }, []);

  const signInWithGoogle = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithGoogle();
      setState({
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      });
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Google Sign-In failed.',
      }));
      throw err;
    }
  }, []);

  const signInWithApple = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithApple();
      setState({
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      });
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Apple Sign-In failed.',
      }));
      throw err;
    }
  }, []);

  const signOut = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      await authService.signOut();
    } finally {
      setState({
        user: null,
        session: null,
        isLoading: false,
        isAuthenticated: false,
        error: null,
      });
    }
  }, []);

  const resetPassword = useCallback(async (email: string) => {
    try {
      return await authService.resetPassword(email);
    } catch (err: any) {
      const msg = err.message || 'Unable to process password reset request.';
      setState((prev) => ({ ...prev, error: msg }));
      throw err;
    }
  }, []);

  const value: AuthContextType = {
    user: state.user,
    session: state.session,
    isLoading: state.isLoading,
    isAuthenticated: state.isAuthenticated,
    error: state.error,
    signIn,
    signUp,
    signInWithGoogle,
    signInWithApple,
    signOut,
    resetPassword,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
