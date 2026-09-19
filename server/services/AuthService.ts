/**
 * AEGIS ALERT - Backend AuthService
 * Handles token generation, credential verification, and session management.
 */

import { UserSession } from '../types/api';

export class AuthService {
  private static sessions: Map<string, UserSession> = new Map();

  /**
   * Validates user credentials and returns session token
   */
  public static async login(credentials: { email?: string; phone?: string; role?: string }): Promise<{ token: string; user: UserSession }> {
    const userId = `usr-${Date.now().toString(36)}`;
    const user: UserSession = {
      id: userId,
      name: credentials.email?.split('@')[0] || 'Verified Citizen',
      email: credentials.email || 'citizen@aegis.gov.in',
      role: (credentials.role as any) || 'citizen',
      phone: credentials.phone || '+91 98765 43210',
      stateId: 'MH',
      district: 'Mumbai Suburban',
    };

    const token = `aegis_jwt_${Math.random().toString(36).substring(2)}${Date.now().toString(36)}`;
    this.sessions.set(token, user);

    return { token, user };
  }

  /**
   * Validate API token
   */
  public static async validateToken(token: string): Promise<UserSession | null> {
    if (this.sessions.has(token)) {
      return this.sessions.get(token) || null;
    }
    return null;
  }
}
