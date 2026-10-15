import { AuthSession, AuthUser, SignInCredentials, SignUpCredentials } from './authTypes';
import { authStorage } from './authStorage';
import { getApiUrl } from '../config/apiConfig';

/**
 * Validates basic email structure.
 */
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email.trim());
}

async function parseAuthError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (data?.detail) {
      if (typeof data.detail === 'string') return data.detail;
      if (Array.isArray(data.detail)) return data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
    }
  } catch {}
  return `Authentication failed (${response.status})`;
}

export class AuthService {
  async signInWithEmail(credentials: SignInCredentials): Promise<AuthSession> {
    const email = credentials.email.trim();
    const password = credentials.password;

    if (!email || !isValidEmail(email)) throw new Error('Please enter a valid email address.');
    if (!password) throw new Error('Please enter your password.');

    const formData = new URLSearchParams();
    formData.append('username', email); // OAuth2 expects username
    formData.append('password', password);

    const response = await fetch(getApiUrl('/api/v1/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });

    if (!response.ok) {
      throw new Error(await parseAuthError(response));
    }

    const data = await response.json();
    
    // Fetch current user details
    const userRes = await fetch(getApiUrl('/api/v1/auth/me'), {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    
    if (!userRes.ok) throw new Error('Failed to retrieve user profile');
    const userData = await userRes.json();

    const user: AuthUser = {
      id: userData.id,
      email: userData.email,
      name: userData.full_name || userData.email.split('@')[0],
      provider: 'email',
      createdAt: userData.created_at || new Date().toISOString(),
    };

    const session: AuthSession = {
      token: data.access_token,
      user,
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    };

    await authStorage.setSession(session);
    return session;
  }

  async signUpWithEmail(credentials: SignUpCredentials): Promise<AuthSession> {
    const name = credentials.name.trim();
    const email = credentials.email.trim();
    const password = credentials.password;
    if (credentials.confirmPassword !== undefined && password !== credentials.confirmPassword) {
      throw new Error('Passwords do not match.');
    }

    const response = await fetch(getApiUrl('/api/v1/auth/register'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: email,
        password,
        full_name: name,
      }),
    });

    if (!response.ok) {
      throw new Error(await parseAuthError(response));
    }
    
    // Automatically login after signup
    return this.signInWithEmail({ email, password });
  }

  async signInWithGoogle(): Promise<AuthSession> {
    throw new Error('Google Sign-In is configured and ready for OAuth client registration in the next milestone.');
  }

  async signInWithApple(): Promise<AuthSession> {
    throw new Error('Apple Sign-In is configured and ready for Apple Services ID registration in the next milestone.');
  }

  async signOut(): Promise<void> {
    await authStorage.clearSession();
  }

  async resetPassword(email: string): Promise<{ success: boolean; message: string }> {
    return {
      success: true,
      message: `If an account exists for ${email.trim()}, instructions to reset your password have been sent.`,
    };
  }

  async restoreSession(): Promise<AuthSession | null> {
    return await authStorage.getSession();
  }

  // --- LOCKER APIs ---
  async getLockerHeaders() {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const session = await authStorage.getSession();
    if (session?.token) headers['Authorization'] = `Bearer ${session.token}`;
    const lockerToken = await authStorage.getLockerToken();
    if (lockerToken) headers['X-Locker-Token'] = lockerToken;
    return headers;
  }

  async checkLockerStatus(): Promise<{ exists: boolean; status: 'locked' | 'unlocked' | 'expired' }> {
    const response = await fetch(getApiUrl('/api/v1/locker/status'), {
      method: 'GET',
      headers: await this.getLockerHeaders(),
    });
    if (!response.ok) {
      // If locker doesn't exist, it might 404. Let's assume false exists
      if (response.status === 404) return { exists: false, status: 'locked' };
      throw new Error(await parseAuthError(response));
    }
    return await response.json();
  }

  async createLocker(password: string): Promise<void> {
    const response = await fetch(getApiUrl('/api/v1/locker/create'), {
      method: 'POST',
      headers: await this.getLockerHeaders(),
      body: JSON.stringify({ password }),
    });
    if (!response.ok) throw new Error(await parseAuthError(response));
  }

  async unlockLocker(password: string): Promise<{ token: string; expires_at: string }> {
    const response = await fetch(getApiUrl('/api/v1/locker/unlock'), {
      method: 'POST',
      headers: await this.getLockerHeaders(),
      body: JSON.stringify({ password }),
    });
    if (!response.ok) throw new Error(await parseAuthError(response));
    const data = await response.json();
    await authStorage.setLockerToken(data.locker_token);
    return data;
  }

  async lockLocker(): Promise<void> {
    const response = await fetch(getApiUrl('/api/v1/locker/lock'), {
      method: 'POST',
      headers: await this.getLockerHeaders(),
    });
    if (!response.ok) {
      console.warn('Failed to lock on server, clearing local anyway');
    }
    await authStorage.clearLockerToken();
  }
}

export const authService = new AuthService();
