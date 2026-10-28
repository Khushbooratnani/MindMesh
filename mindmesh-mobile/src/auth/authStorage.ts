import { AuthSession, AuthUser } from './authTypes';

/**
 * Storage interface for persisting active authentication sessions.
 * Never stores plaintext passwords or sensitive credentials.
 */
export interface IAuthStorage {
  getSession(): Promise<AuthSession | null>;
  setSession(session: AuthSession): Promise<void>;
  clearSession(): Promise<void>;
  getUser(): Promise<AuthUser | null>;

  getLockerToken(): Promise<string | null>;
  setLockerToken(token: string): Promise<void>;
  clearLockerToken(): Promise<void>;
}

class MemoryAuthStorage implements IAuthStorage {
  private activeSession: AuthSession | null = null;
  private lockerToken: string | null = null;

  async getSession(): Promise<AuthSession | null> {
    if (!this.activeSession) {
      return null;
    }
    // Check if session token has expired
    const expiresAt = new Date(this.activeSession.expiresAt).getTime();
    if (expiresAt < Date.now()) {
      this.activeSession = null;
      return null;
    }
    return this.activeSession;
  }

  async setSession(session: AuthSession): Promise<void> {
    this.activeSession = session;
  }

  async clearSession(): Promise<void> {
    this.activeSession = null;
    this.lockerToken = null; // Also clear locker on logout
  }

  async getUser(): Promise<AuthUser | null> {
    const session = await this.getSession();
    return session ? session.user : null;
  }

  async getLockerToken(): Promise<string | null> {
    return this.lockerToken;
  }

  async setLockerToken(token: string): Promise<void> {
    this.lockerToken = token;
  }

  async clearLockerToken(): Promise<void> {
    this.lockerToken = null;
  }
}

export const authStorage: IAuthStorage = new MemoryAuthStorage();
