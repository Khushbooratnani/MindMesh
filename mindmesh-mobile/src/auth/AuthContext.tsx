import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode, useRef } from 'react';
import {
  AuthContextType,
  AuthState,
  SignInCredentials,
  SignUpCredentials,
} from './authTypes';
import { authService } from './authService';
import { deviceKeyManager } from '../local_first/deviceKeyManager';

const initialState: AuthState = {
  user: null,
  session: null,
  isLoading: true,
  isAuthenticated: false,
  error: null,
  lockerExists: false,
  isLockerUnlocked: false,
  lockerExpiresAt: null,
  isLockerLoading: false,
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>(initialState);
  
  const lockerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkLocker = useCallback(async () => {
    setState((prev) => ({ ...prev, isLockerLoading: true }));
    try {
      const status = await authService.checkLockerStatus();
      setState((prev) => ({
        ...prev,
        lockerExists: status.exists,
        isLockerUnlocked: status.status === 'unlocked',
        isLockerLoading: false,
      }));
    } catch (err: any) {
      console.warn("Locker status check failed:", err.message);
      setState((prev) => ({ ...prev, isLockerLoading: false }));
    }
  }, []);

  // Restore active session on initial app mount
  useEffect(() => {
    let isMounted = true;
    const initAuth = async () => {
      try {
        const session = await authService.restoreSession();
        if (isMounted) {
          if (session) {
            setState((prev) => ({
              ...prev,
              user: session.user,
              session,
              isLoading: false,
              isAuthenticated: true,
              error: null,
            }));
            await checkLocker();
          } else {
            setState((prev) => ({
              ...prev,
              user: null,
              session: null,
              isLoading: false,
              isAuthenticated: false,
              error: null,
            }));
          }
        }
      } catch {
        if (isMounted) {
          setState((prev) => ({
            ...prev,
            user: null,
            session: null,
            isLoading: false,
            isAuthenticated: false,
            error: null,
          }));
        }
      }
    };

    initAuth();
    return () => {
      isMounted = false;
    };
  }, [checkLocker]);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const signIn = useCallback(async (credentials: SignInCredentials) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithEmail(credentials);
      setState((prev) => ({
        ...prev,
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      }));
      await checkLocker();
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Authentication failed. Please check your credentials.',
      }));
      throw err;
    }
  }, [checkLocker]);

  const signUp = useCallback(async (credentials: SignUpCredentials) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signUpWithEmail(credentials);
      setState((prev) => ({
        ...prev,
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      }));
      await checkLocker();
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Account creation failed. Please try again.',
      }));
      throw err;
    }
  }, [checkLocker]);

  const signInWithGoogle = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithGoogle();
      setState((prev) => ({
        ...prev,
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      }));
      await checkLocker();
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Google Sign-In failed.',
      }));
      throw err;
    }
  }, [checkLocker]);

  const signInWithApple = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const session = await authService.signInWithApple();
      setState((prev) => ({
        ...prev,
        user: session.user,
        session,
        isLoading: false,
        isAuthenticated: true,
        error: null,
      }));
      await checkLocker();
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err.message || 'Apple Sign-In failed.',
      }));
      throw err;
    }
  }, [checkLocker]);

  const lockLocker = useCallback(async () => {
    try {
      await authService.lockLocker();
    } catch {
      // ignore server errors during lock
    } finally {
      deviceKeyManager.lockLocker();
      if (lockerTimerRef.current) clearTimeout(lockerTimerRef.current);
      setState((prev) => ({
        ...prev,
        isLockerUnlocked: false,
        lockerExpiresAt: null,
      }));
    }
  }, []);

  const unlockLocker = useCallback(async (password: string) => {
    setState((prev) => ({ ...prev, isLockerLoading: true, error: null }));
    try {
      const { expires_at } = await authService.unlockLocker(password);
      // Unlock local device encryption key
      try {
        await deviceKeyManager.unlockWithPassword(password);
      } catch (keyErr) {
        console.warn('[AuthContext] Local device key unlock warning:', keyErr);
      }
      setState((prev) => ({
        ...prev,
        isLockerUnlocked: true,
        lockerExpiresAt: expires_at,
        isLockerLoading: false,
      }));
      // Set 120s timeout
      if (lockerTimerRef.current) clearTimeout(lockerTimerRef.current);
      lockerTimerRef.current = setTimeout(() => {
        lockLocker();
      }, 120 * 1000);
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLockerLoading: false,
        error: err.message || 'Failed to unlock locker.',
      }));
      throw err;
    }
  }, [lockLocker]);

  const createLocker = useCallback(async (password: string) => {
    setState((prev) => ({ ...prev, isLockerLoading: true, error: null }));
    try {
      const res = await authService.createLocker(password);
      try {
        await deviceKeyManager.initializeNewLockerKey(password);
      } catch (keyErr) {
        console.warn('[AuthContext] Local device key initialization warning:', keyErr);
      }
      await checkLocker();
      return res;
    } catch (err: any) {
      setState((prev) => ({
        ...prev,
        isLockerLoading: false,
        error: err.message || 'Failed to create locker.',
      }));
      throw err;
    }
  }, [checkLocker]);

  const signOut = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      await authService.signOut();
      deviceKeyManager.lockLocker();
      if (lockerTimerRef.current) clearTimeout(lockerTimerRef.current);
    } finally {
      setState({
        ...initialState,
        isLoading: false,
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

  const resetLockerTimer = useCallback(() => {
    if (state.isLockerUnlocked) {
      if (lockerTimerRef.current) clearTimeout(lockerTimerRef.current);
      lockerTimerRef.current = setTimeout(() => {
        lockLocker();
      }, 120 * 1000);
    }
  }, [state.isLockerUnlocked, lockLocker]);

  const value: AuthContextType = {
    ...state,
    signIn,
    signUp,
    signInWithGoogle,
    signInWithApple,
    signOut,
    resetPassword,
    clearError,
    checkLocker,
    createLocker,
    unlockLocker,
    lockLocker,
    resetLockerTimer,
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
