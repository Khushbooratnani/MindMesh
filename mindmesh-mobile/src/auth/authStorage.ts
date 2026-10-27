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
}

class MemoryAuthStorage implements IAuthStorage {
  private activeSession: AuthSession | null = null;

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
  }

  async getUser(): Promise<AuthUser | null> {
    const session = await this.getSession();
    return session ? session.user : null;
  }
}

export const authStorage: IAuthStorage = new MemoryAuthStorage();
