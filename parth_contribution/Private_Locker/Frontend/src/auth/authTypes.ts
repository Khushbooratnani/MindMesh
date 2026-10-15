export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string | null;
  provider: 'email' | 'google' | 'apple';
  createdAt: string;
}

export interface AuthSession {
  token: string;
  user: AuthUser;
  expiresAt: string;
  refreshToken?: string;
}

export interface AuthState {
  user: AuthUser | null;
  session: AuthSession | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  
  // Locker states
  lockerExists: boolean;
  isLockerUnlocked: boolean;
  lockerExpiresAt: string | null;
  isLockerLoading: boolean;
}

export interface SignInCredentials {
  email: string;
  password: string;
}

export interface SignUpCredentials {
  name: string;
  email: string;
  password: string;
  confirmPassword?: string;
}

export interface AuthContextType extends AuthState {
  signIn: (credentials: SignInCredentials) => Promise<void>;
  signUp: (credentials: SignUpCredentials) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signInWithApple: () => Promise<void>;
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<{ success: boolean; message: string }>;
  clearError: () => void;

  // Locker functions
  checkLocker: () => Promise<void>;
  createLocker: (password: string) => Promise<void>;
  unlockLocker: (password: string) => Promise<void>;
  lockLocker: () => Promise<void>;
  resetLockerTimer: () => void;
}
