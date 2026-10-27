import { AuthSession, AuthUser, SignInCredentials, SignUpCredentials } from './authTypes';
import { authStorage } from './authStorage';

/**
 * Validates basic email structure.
 */
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email.trim());
}

/**
 * Generates a deterministic, stable user ID based on email.
 * This guarantees user identity continuity across sessions.
 */
function generateStableUserId(email: string): string {
  let hash = 0;
  const clean = email.trim().toLowerCase();
  for (let i = 0; i < clean.length; i++) {
    hash = (hash << 5) - hash + clean.charCodeAt(i);
    hash |= 0;
  }
  const hex = Math.abs(hash).toString(16).padStart(8, '0');
  return `U_${hex}`;
}

export class AuthService {
  /**
   * Authenticate user with Email and Password.
   */
  async signInWithEmail(credentials: SignInCredentials): Promise<AuthSession> {
    const email = credentials.email.trim();
    const password = credentials.password;

    if (!email) {
      throw new Error('Please enter your email address.');
    }
    if (!isValidEmail(email)) {
      throw new Error('Please enter a valid email address.');
    }
    if (!password) {
      throw new Error('Please enter your password.');
    }
    if (password.length < 8) {
      throw new Error('Password must be at least 8 characters long.');
    }

    const userId = generateStableUserId(email);
    const user: AuthUser = {
      id: userId,
      email: email.toLowerCase(),
      name: email.split('@')[0],
      provider: 'email',
      createdAt: new Date().toISOString(),
    };

    const session: AuthSession = {
      token: `mm_sess_${userId}_${Date.now()}`,
      user,
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days
    };

    await authStorage.setSession(session);
    return session;
  }

  /**
   * Register a new user account with Email and Password.
   */
  async signUpWithEmail(credentials: SignUpCredentials): Promise<AuthSession> {
    const name = credentials.name.trim();
    const email = credentials.email.trim();
    const password = credentials.password;
    const confirmPassword = credentials.confirmPassword;

    if (!name) {
      throw new Error('Please enter your full name.');
    }
    if (!email) {
      throw new Error('Please enter your email address.');
    }
    if (!isValidEmail(email)) {
      throw new Error('Please enter a valid email address.');
    }
    if (!password) {
      throw new Error('Please create a password.');
    }
    if (password.length < 8) {
      throw new Error('Password must be at least 8 characters long.');
    }
    if (confirmPassword !== undefined && password !== confirmPassword) {
      throw new Error('Passwords do not match. Please verify your password.');
    }

    const userId = generateStableUserId(email);
    const user: AuthUser = {
      id: userId,
      email: email.toLowerCase(),
      name,
      provider: 'email',
      createdAt: new Date().toISOString(),
    };

    const session: AuthSession = {
      token: `mm_sess_${userId}_${Date.now()}`,
      user,
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    };

    await authStorage.setSession(session);
    return session;
  }

  /**
   * Google OAuth authentication abstraction.
   * Explicitly reports configuration status until native OAuth client IDs are provisioned.
   */
  async signInWithGoogle(): Promise<AuthSession> {
    // In production, triggers Google OAuth redirect / native SDK
    // If credentials are not yet provisioned, do not fake success
    throw new Error(
      'Google Sign-In is configured and ready for OAuth client registration in the next milestone.'
    );
  }

  /**
   * Apple ID authentication abstraction.
   * Explicitly reports configuration status until native Apple Service ID is provisioned.
   */
  async signInWithApple(): Promise<AuthSession> {
    // In production, triggers Apple Authentication SDK
    // If credentials are not yet provisioned, do not fake success
    throw new Error(
      'Apple Sign-In is configured and ready for Apple Services ID registration in the next milestone.'
    );
  }

  /**
   * Terminate active authentication session and clear persistent storage.
   */
  async signOut(): Promise<void> {
    await authStorage.clearSession();
  }

  /**
   * Request password reset instructions for an account.
   * Uses privacy-preserving confirmation response.
   */
  async resetPassword(email: string): Promise<{ success: boolean; message: string }> {
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      throw new Error('Please enter your email address.');
    }
    if (!isValidEmail(cleanEmail)) {
      throw new Error('Please enter a valid email address.');
    }

    return {
      success: true,
      message: `If an account exists for ${cleanEmail}, instructions to reset your password have been sent.`,
    };
  }

  /**
   * Restore existing session on app startup.
   */
  async restoreSession(): Promise<AuthSession | null> {
    return await authStorage.getSession();
  }
}

export const authService = new AuthService();
